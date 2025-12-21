import { Injectable, inject } from '@angular/core';
import { Observable, of, Subject } from 'rxjs';
import { debounceTime, switchMap, map, catchError, distinctUntilChanged } from 'rxjs/operators';
import { ApiService } from './api.service';
import { API_CONFIG } from '../config/api.config';
import { SearchResponse } from '../models/search.model';

export interface Suggestion {
  id: string;
  query: string;
  url: string;
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
  readonly MAX_SUGGESTIONS = 10;

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
    return response.results.map(result => ({
      id: result._id,
      query: result._source.url_query,
      url: result._source.capture.url,
    }));
  }

  /**
   * Clears any pending search
   */
  clear(): void {
    this.searchSubject.next('');
  }
}
