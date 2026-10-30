import { Injectable, inject } from '@angular/core';
import { Observable, catchError, forkJoin, map, of, shareReplay } from 'rxjs';
import { AqlApiClient } from '../api/client';
import { components } from '../api/schema';
import { ProviderStatistics } from '../models/statistics.model';
import { SearchService, SerpFilterParams, toHistogramItems } from './search.service';

export type ProviderResponse = components['schemas']['Provider'];

export interface ProviderDetail {
  id: string;
  name: string;
  domains?: string[];
  priority?: number;
  url_patterns: string[];
}

/**
 * Maximum number of providers to fetch at once (Elasticsearch's default result window).
 */
const MAX_PROVIDERS = 10000;

function toProviderDetail(provider: ProviderResponse): ProviderDetail {
  return {
    id: provider._id,
    name: provider.name,
    domains: provider.domains,
    priority: provider.priority ?? undefined,
    url_patterns: provider.url_path_prefixes,
  };
}

@Injectable({
  providedIn: 'root',
})
export class ProviderService {
  private readonly api = inject(AqlApiClient);
  private readonly searchService = inject(SearchService);
  // Cache the providers response to avoid multiple API calls
  private providersCache$?: Observable<ProviderDetail[]>;

  /**
   * Fetch all available providers from the backend.
   * Results are cached to avoid redundant API calls.
   */
  getProviders(): Observable<ProviderDetail[]> {
    if (!this.providersCache$) {
      this.providersCache$ = this.api
        .request((client, signal) =>
          client.GET('/providers/', { params: { query: { size: MAX_PROVIDERS } }, signal }),
        )
        .pipe(
          map(response => response.map(toProviderDetail)),
          // Sort providers alphabetically by name
          map(providers => providers.sort((a, b) => a.name.localeCompare(b.name))),
          // Cache the result and share among subscribers
          shareReplay(1),
          catchError(error => {
            // Use warn to avoid failing tests that run without backend available
            console.warn('Failed to fetch providers:', error);
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
    return this.api
      .request((client, signal) =>
        client.GET('/providers/{id}', { params: { path: { id: providerId } }, signal }),
      )
      .pipe(
        map(response => (response ? toProviderDetail(response) : null)),
        catchError(error => {
          // Use warn to reduce test noise when backend isn't available in CI
          console.warn(`Failed to fetch provider ${providerId}:`, error);
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
   * Fetch statistics for a specific provider, aggregated from the provider's SERPs.
   */
  getProviderStatistics(providerId: string): Observable<ProviderStatistics> {
    const filterParams: SerpFilterParams = { provider_id: providerId };
    return forkJoin({
      serp_count: this.searchService.count(filterParams),
      unique_queries_count: this.searchService.countUnique(filterParams),
      top_archives: this.searchService.topArchives(filterParams, 5),
      date_histogram: this.searchService.dateHistogram(filterParams, 'month'),
    }).pipe(
      map(statistics => ({
        provider_id: providerId,
        serp_count: statistics.serp_count,
        unique_queries_count: statistics.unique_queries_count,
        date_histogram: toHistogramItems(statistics.date_histogram),
        top_archives: statistics.top_archives.map(bucket => ({
          archive: bucket.archive.name,
          count: bucket.count,
        })),
      })),
    );
  }
}
