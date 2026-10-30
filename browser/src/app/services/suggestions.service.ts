import { Injectable, Signal, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  debounceTime,
  distinctUntilChanged,
  switchMap,
  catchError,
  map,
  shareReplay,
} from 'rxjs/operators';
import { Observable, of, Subject } from 'rxjs';
import { QuerySuggestion } from '../models/search.model';
import { SearchService } from './search.service';

export interface Suggestion {
  id: string;
  query: string;
  /** Number of SERPs with the suggested query. */
  score?: number | null;
}

@Injectable({
  providedIn: 'root',
})
export class SuggestionsService {
  readonly MINIMUM_QUERY_LENGTH = 3;
  readonly DEBOUNCE_TIME_MS = 300;
  readonly MAX_SUGGESTIONS = 5;
  readonly suggestions: Signal<Suggestion[]>;

  private readonly searchService = inject(SearchService);
  private readonly searchSubject = new Subject<string>();

  constructor() {
    // Shared suggestions observable (single backend call per input)
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
  }

  search(query: string): void {
    this.searchSubject.next(query);
  }

  private fetchSuggestions(query: string): Observable<Suggestion[]> {
    return this.searchService.suggestQueries(query, this.MAX_SUGGESTIONS).pipe(
      map(suggestions => this.mapCompletionsToSuggestions(suggestions.completions)),
      catchError(() => of([])),
    );
  }

  private mapCompletionsToSuggestions(completions: QuerySuggestion[]): Suggestion[] {
    const seen = new Set<string>();
    const unique: Suggestion[] = [];

    for (const completion of completions) {
      const query = completion.text;
      if (seen.has(query)) continue;
      seen.add(query);
      unique.push({ id: query, query, score: completion.frequency });
      if (unique.length >= this.MAX_SUGGESTIONS) break;
    }

    return unique;
  }
}
