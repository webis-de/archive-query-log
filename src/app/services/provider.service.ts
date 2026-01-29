import { Injectable, inject } from '@angular/core';
import { Observable, catchError, map, of, shareReplay } from 'rxjs';
import { ApiService } from './api.service';
import { API_CONFIG } from '../config/api.config';
import { ProviderStatistics } from '../models/statistics.model';

export interface ProviderResponse {
  _id: string;
  _source: {
    name: string;
    [key: string]: unknown;
  };
}

export interface ProvidersApiResponse {
  count: number;
  results: ProviderResponse[];
}

export interface ProviderDetail {
  id: string;
  name: string;
  domains?: string[];
  priority?: number;
  url_patterns: string[];
}

/**
 * Response from the provider detail API endpoint
 */
export interface ProviderDetailResponse {
  provider_id: string;
  provider: {
    _id: string;
    _source: {
      name: string;
      domains?: string[];
      url_patterns?: string[];
      priority?: number;
      [key: string]: unknown;
    };
  };
}

@Injectable({
  providedIn: 'root',
})
export class ProviderService {
  private readonly apiService = inject(ApiService);
  // Cache the providers response to avoid multiple API calls
  private providersCache$?: Observable<ProviderDetail[]>;

  /**
   * Fetch all available providers from the backend.
   * Results are cached to avoid redundant API calls.
   */
  getProviders(): Observable<ProviderDetail[]> {
    if (!this.providersCache$) {
      this.providersCache$ = this.apiService
        .get<ProvidersApiResponse>(API_CONFIG.endpoints.providers)
        .pipe(
          map(response =>
            response.results.map(provider => ({
              id: provider._id,
              name: provider._source.name,
              domains: provider._source['domains'] as string[],
              priority: provider._source['priority'] as number,
              url_patterns: provider._source['url_patterns'] as string[],
            })),
          ),
          // Sort providers alphabetically by name
          map(providers => providers.sort((a, b) => a.name.localeCompare(b.name))),
          // Cache the result and share among subscribers
          shareReplay(1),
          catchError(error => {
            console.error('Failed to fetch providers:', error);
            // Clear cache on error so it can be retried
            this.providersCache$ = undefined;
            return of([]);
          }),
        );
    }
    return this.providersCache$;
  }

  /**
   * Clear the providers cache to force a fresh fetch on next call.
   */
  clearCache(): void {
    this.providersCache$ = undefined;
  }

  /**
   * Fetch a specific provider by ID from the backend.
   * Returns the full provider metadata including domains and URL patterns.
   */
  getProviderById(providerId: string): Observable<ProviderDetail | null> {
    return this.apiService
      .get<ProviderDetailResponse>(API_CONFIG.endpoints.provider(providerId))
      .pipe(
        map(response => ({
          id: response.provider._id,
          name: response.provider._source.name,
          domains: response.provider._source.domains || [],
          url_patterns: response.provider._source.url_patterns || [],
          priority: response.provider._source.priority,
        })),
        catchError(error => {
          console.error(`Failed to fetch provider ${providerId}:`, error);
          return of(null);
        }),
      );
  }

  /**
   * Search providers by query string.
   * Filters the cached providers list client-side.
   */
  searchProviders(query: string): Observable<ProviderDetail[]> {
    return this.getProviders().pipe(
      map(providers => {
        if (!query.trim()) return providers;
        const lowerQuery = query.toLowerCase();
        return providers.filter(provider => provider.name.toLowerCase().includes(lowerQuery));
      }),
    );
  }

  /**
   * Fetch statistics for a specific provider.
   */
  getProviderStatistics(providerId: string): Observable<ProviderStatistics> {
    return this.apiService.get<ProviderStatistics>(
      API_CONFIG.endpoints.providerStatistics(encodeURIComponent(providerId)),
    );
  }
}
