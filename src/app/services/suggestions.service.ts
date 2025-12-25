import { Injectable, inject } from '@angular/core';
import { Observable, of, Subject } from 'rxjs';
import { debounceTime, switchMap, map, catchError, distinctUntilChanged } from 'rxjs/operators';
import { ApiService } from './api.service';
import { API_CONFIG } from '../config/api.config';
import { SearchResponse } from '../models/search.model';

export interface Suggestion {
  id: string;
  query: string;
}

@Injectable({
  providedIn: 'root',
})
export class SuggestionsService {
  private readonly apiService = inject(ApiService);
  private readonly searchSubject = new Subject<string>();

  // TODO Number of suggestion
  readonly MINIMUM_QUERY_LENGTH = 3;
  readonly DEBOUNCE_TIME_MS = 300;
  readonly MAX_SUGGESTIONS = 5;

  /**
   * Creates an observable that emits suggestions based on query input.
   * Automatically debounces and filters queries less than minimum length.
   */
  getSuggestions$(): Observable<Suggestion[]> {
    return this.searchSubject.pipe(
      debounceTime(this.DEBOUNCE_TIME_MS),
      distinctUntilChanged(),
      switchMap(query => {
        if (query.length < this.MINIMUM_QUERY_LENGTH) {
          return of([]);
        }
        return this.fetchSuggestions(query);
      }),
    );
  }

  /**
   * Triggers a new suggestion search
   */
  search(query: string): void {
    this.searchSubject.next(query);
  }

  /**
   * Fetches suggestions from the API
   */
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
   * Maps search results to suggestion format
   */
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

  /**
   * Clears any pending search
   */
  clear(): void {
    this.searchSubject.next('');
  }
}
