import { Injectable, Signal, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  debounceTime,
  distinctUntilChanged,
  switchMap,
  catchError,
  map,
  shareReplay,
  tap,
  retryWhen,
  mergeMap,
  finalize,
} from 'rxjs/operators';
import { Observable, of, Subject, combineLatest, concat, timer, throwError } from 'rxjs';
import { ApiService } from './api.service';
import { API_CONFIG } from '../config/api.config';
import { SearchResponse, QueryMetadataResponse } from '../models/search.model';
import { SearchService } from './search.service';

export interface Suggestion {
  id: string;
  query: string;
  // optional preview metadata fields
  score?: number | null; // total hits for this suggestion
  top_provider?: string | null;
  top_archive?: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class SuggestionsService {
  readonly MINIMUM_QUERY_LENGTH = 3;
  readonly DEBOUNCE_TIME_MS = 300;
  readonly MAX_SUGGESTIONS = 5;
  readonly suggestions: Signal<Suggestion[]>;

  readonly suggestionsWithMeta: Signal<Suggestion[]>;

  private readonly apiService = inject(ApiService);
  private readonly searchService = inject(SearchService);
  private readonly searchSubject = new Subject<string>();

  // cache for preview metadata per query
  private readonly metadataCache = new Map<string, QueryMetadataResponse>();
  // in-flight metadata requests deduplication
  private readonly inFlightMetadata = new Map<string, Observable<QueryMetadataResponse>>();
  // retry/backoff configuration for 429 responses
  private readonly META_MAX_RETRIES = 3;
  private readonly META_BASE_DELAY_MS = 100; // exponential backoff base (100ms)
  // cooldown: when the backend responds with too many requests, temporarily suspend metadata fetches
  private readonly META_COOLDOWN_MS = 2000; // 2s cooldown
  private metadataCooldownUntil = 0;

  constructor() {
    // Shared suggestions observable (single backend search call per input)
    const suggestions$ = this.searchSubject.pipe(
      debounceTime(this.DEBOUNCE_TIME_MS),
      distinctUntilChanged(),
      switchMap(query => {
        if (query.length < this.MINIMUM_QUERY_LENGTH) {
          return of([] as Suggestion[]);
        }
        return this.fetchSuggestions(query);
      }),
      // ensure multiple subscribers reuse same result and avoid extra network calls
      shareReplay({ bufferSize: 1, refCount: true }),
    );

    this.suggestions = toSignal(suggestions$, { initialValue: [] as Suggestion[] });

    // derive suggestionsWithMeta from the shared suggestions stream and augment with metadata
    this.suggestionsWithMeta = toSignal(
      suggestions$.pipe(
        switchMap(suggestions => {
          if (!suggestions || suggestions.length === 0) return of([] as Suggestion[]);
          return this.addMetaToSuggestions(suggestions);
        }),
      ),
      { initialValue: [] as Suggestion[] },
    );
  }

  search(query: string): void {
    this.searchSubject.next(query);
  }

  private fetchSuggestions(query: string): Observable<Suggestion[]> {
    const params: Record<string, string | number> = {
      query: query,
      size: this.MAX_SUGGESTIONS,
    };

    return this.apiService.get<SearchResponse>(API_CONFIG.endpoints.serps, params).pipe(
      map(response => this.mapResultsToSuggestions(response)),
      catchError(() => of([])),
    );
  }

  /**
   * Augment a set of suggestions with preview metadata using a cache to avoid duplicate backend calls
   */
  private addMetaToSuggestions(suggestions: Suggestion[]): Observable<Suggestion[]> {
    // Stagger metadata fetches: top suggestion immediately, others after incremental delays (150ms * index)
    const metadataStreams = suggestions.map((s, idx) => {
      const delayMs = idx === 0 ? 0 : 150 * idx;
      // emit null immediately so combineLatest emits early, then fetch metadata after a delay
      return concat(of(null), timer(delayMs).pipe(switchMap(() => this.getMetadata(s.query))));
    });

    return combineLatest(metadataStreams).pipe(
      map((metas: (QueryMetadataResponse | null)[]) => {
        return suggestions.map((s, i) => ({
          ...s,
          score: metas[i]?.total_hits ?? null,
          top_provider: metas[i]?.top_providers?.[0]?.provider ?? null,
          top_archive: metas[i]?.top_archives?.[0]?.archive ?? null,
        }));
      }),
      catchError(() => of([] as Suggestion[])),
    );
  }

  /**
   * Get metadata for a query from cache or backend and cache the result
   */
  private getMetadata(query: string) {
    // if we are in cooldown due to frequent 429 responses, return default metadata
    if (Date.now() < this.metadataCooldownUntil) {
      return of({
        query,
        total_hits: 0,
        top_queries: [],
        date_histogram: [],
        top_providers: [],
        top_archives: [],
      } as QueryMetadataResponse);
    }

    if (this.metadataCache.has(query)) {
      return of(this.metadataCache.get(query) as QueryMetadataResponse);
    }

    if (this.inFlightMetadata.has(query)) {
      return this.inFlightMetadata.get(query) as Observable<QueryMetadataResponse>;
    }

    const request$ = this.searchService
      .getQueryMetadata({ query, top_providers: 1, top_archives: 1 })
      .pipe(
        // retry only on 429 Too Many Requests with exponential backoff
        retryWhen(error$ =>
          error$.pipe(
            mergeMap((err: unknown, i: number) => {
              const attempt = i + 1;
              const status = (err as { status?: number }).status;
              if (status === 429 && attempt <= this.META_MAX_RETRIES) {
                const delayMs = this.META_BASE_DELAY_MS * Math.pow(2, i);
                return timer(delayMs);
              }
              if (status === 429) {
                // enter cooldown to avoid hammering the backend
                this.metadataCooldownUntil = Date.now() + this.META_COOLDOWN_MS;
              }
              return throwError(() => err as unknown);
            }),
          ),
        ),
        tap(result => this.metadataCache.set(query, result)),
        catchError(() =>
          of({
            query,
            total_hits: 0,
            top_queries: [],
            date_histogram: [],
            top_providers: [],
            top_archives: [],
          } as QueryMetadataResponse),
        ),
        finalize(() => this.inFlightMetadata.delete(query)),
        shareReplay({ bufferSize: 1, refCount: true }),
      );

    this.inFlightMetadata.set(query, request$);
    return request$;
  }

  private mapResultsToSuggestions(response: SearchResponse): Suggestion[] {
    const seen = new Set<string>();
    const unique: Suggestion[] = [];

    for (const result of response.results) {
      const query = result._source.url_query;
      if (seen.has(query)) continue;
      seen.add(query);
      unique.push({ id: result._id, query });
      if (unique.length >= this.MAX_SUGGESTIONS) break;
    }

    return unique;
  }
}
