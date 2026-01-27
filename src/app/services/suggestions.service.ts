import { Injectable, Signal, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { debounceTime, distinctUntilChanged, switchMap, catchError, map } from 'rxjs/operators';
import { Observable, of, Subject, forkJoin } from 'rxjs';
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

  constructor() {
    this.suggestions = toSignal(
      this.searchSubject.pipe(
        debounceTime(this.DEBOUNCE_TIME_MS),
        distinctUntilChanged(),
        switchMap(query => {
          if (query.length < this.MINIMUM_QUERY_LENGTH) {
            return of([]);
          }
          return this.fetchSuggestions(query);
        }),
      ),
      { initialValue: [] as Suggestion[] },
    );

    this.suggestionsWithMeta = toSignal(
      this.searchSubject.pipe(
        debounceTime(this.DEBOUNCE_TIME_MS),
        distinctUntilChanged(),
        switchMap(query => {
          if (query.length < this.MINIMUM_QUERY_LENGTH) {
            return of([] as Suggestion[]);
          }
          return this.fetchSuggestionsWithMeta(query);
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
   * Fetch suggestions and augment each with preview metadata (total_hits, top provider/archive)
   */
  private fetchSuggestionsWithMeta(query: string): Observable<Suggestion[]> {
    return this.fetchSuggestions(query).pipe(
      switchMap(suggestions => {
        if (!suggestions || suggestions.length === 0) return of([]);

        const metadataCalls = suggestions.map(sugg =>
          this.searchService.getQueryMetadata({
            query: sugg.query,
            top_providers: 1,
            top_archives: 1,
          }),
        );

        return forkJoin(metadataCalls).pipe(
          map((metas: QueryMetadataResponse[]) => {
            return suggestions.map((s, i) => ({
              ...s,
              score: metas[i]?.total_hits ?? null,
              top_provider: metas[i]?.top_providers?.[0]?.provider ?? null,
              top_archive: metas[i]?.top_archives?.[0]?.archive ?? null,
            }));
          }),
        );
      }),
      catchError(() => of([])),
    );
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
