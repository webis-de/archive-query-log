import { Injectable, inject } from '@angular/core';
import { Observable, catchError, forkJoin, map, of } from 'rxjs';
import { AqlApiClient } from '../api/client';
import { operations } from '../api/schema';
import {
  ArchiveBucket,
  DateHistogramBucket,
  DateHistogramInterval,
  OrganicResult,
  ProviderBucket,
  QueryBucket,
  QuerySuggestion,
  QuerySuggestions,
  SearchResponse,
  SearchResult,
  QueryMetadataResponse,
  QueryMetadataParams,
  SerpDetailsResponse,
  UnbrandedSerp,
  UnfurlData,
} from '../models/search.model';

/**
 * Filters and query shared by the SERP search, count, and aggregation endpoints.
 */
export type SerpFilterParams = NonNullable<operations['count_serps']['parameters']['query']>;

export interface SearchOptions {
  advancedMode?: boolean;
  fuzzy?: boolean;
  /** @deprecated Ignored by the API. */
  fuzziness?: 'AUTO' | '0' | '1' | '2';
  /** @deprecated Ignored by the API. */
  expandSynonyms?: boolean;
  year?: number;
  provider_id?: string;
  status_code?: number;
}

@Injectable({
  providedIn: 'root',
})
export class SearchService {
  private readonly api = inject(AqlApiClient);

  search(
    query: string,
    size?: number,
    page?: number,
    options: SearchOptions = {},
  ): Observable<SearchResponse> {
    const filterParams = this.buildFilterParams(query, options);
    const from_ =
      size !== undefined && page !== undefined && page > 1 ? (page - 1) * size : undefined;

    return forkJoin({
      results: this.api.request((client, signal) =>
        client.GET('/serps/', {
          params: { query: { ...filterParams, size, from_ } },
          signal,
        }),
      ),
      total: this.count(filterParams),
      did_you_mean:
        options.fuzzy || options.expandSynonyms
          ? this.suggestQueries(query).pipe(
              map(suggestions => suggestions.corrections),
              catchError(() => of([] as QuerySuggestion[])),
            )
          : of([] as QuerySuggestion[]),
    });
  }

  /**
   * Aggregate summary statistics for a query from the SERP count, top providers/archives, and date histogram endpoints.
   */
  getQueryMetadata(params: QueryMetadataParams): Observable<QueryMetadataResponse> {
    const filterParams = this.buildFilterParams(params.query, {
      provider_id: params.provider_id,
    });
    if (params.last_n_months !== undefined && params.last_n_months > 0) {
      const from = new Date();
      from.setUTCMonth(from.getUTCMonth() - params.last_n_months);
      filterParams.from_timestamp = from.toISOString();
    }

    return forkJoin({
      total: this.count(filterParams),
      queries: this.topQueries(filterParams, params.top_n_queries ?? 10),
      providers: this.topProviders(filterParams, params.top_providers ?? 5),
      archives: this.topArchives(filterParams, params.top_archives ?? 5),
      histogram: this.dateHistogram(filterParams, params.interval ?? 'month'),
    }).pipe(
      map(({ total, queries, providers, archives, histogram }) => ({
        query: params.query,
        total_hits: total,
        top_queries: queries,
        date_histogram: toHistogramItems(histogram),
        top_providers: providers.map(bucket => ({
          provider: bucket.provider.name,
          count: bucket.count,
        })),
        top_archives: archives.map(bucket => ({
          archive: bucket.archive.name,
          count: bucket.count,
        })),
      })),
    );
  }

  /**
   * Suggest SERP queries for a (partial) query, both as completions (e.g., while typing) and as spelling corrections (e.g., "Did you mean?").
   */
  suggestQueries(query: string, size?: number): Observable<QuerySuggestions> {
    return this.api.request((client, signal) =>
      client.GET('/serps/suggestions', { params: { query: { query, size } }, signal }),
    );
  }

  /**
   * Get the most common queries among the SERPs matching the given filters.
   */
  topQueries(filterParams: SerpFilterParams, size: number): Observable<QueryBucket[]> {
    return this.api.request((client, signal) =>
      client.GET('/serps/top-queries', { params: { query: { ...filterParams, size } }, signal }),
    );
  }

  /**
   * Count the SERPs matching the given filters.
   */
  count(filterParams: SerpFilterParams): Observable<number> {
    return this.api.request((client, signal) =>
      client.GET('/serps/count', { params: { query: filterParams }, signal }),
    );
  }

  /**
   * Count the unique queries among the SERPs matching the given filters.
   */
  countUnique(filterParams: SerpFilterParams): Observable<number> {
    return this.api.request((client, signal) =>
      client.GET('/serps/count-unique', { params: { query: filterParams }, signal }),
    );
  }

  /**
   * Get the most common search providers among the SERPs matching the given filters.
   */
  topProviders(filterParams: SerpFilterParams, size: number): Observable<ProviderBucket[]> {
    return this.api.request((client, signal) =>
      client.GET('/serps/top-providers', { params: { query: { ...filterParams, size } }, signal }),
    );
  }

  /**
   * Get the most common web archives among the SERPs matching the given filters.
   */
  topArchives(filterParams: SerpFilterParams, size: number): Observable<ArchiveBucket[]> {
    return this.api.request((client, signal) =>
      client.GET('/serps/top-archives', { params: { query: { ...filterParams, size } }, signal }),
    );
  }

  /**
   * Get a date histogram of the SERPs matching the given filters.
   */
  dateHistogram(
    filterParams: SerpFilterParams,
    interval: DateHistogramInterval,
  ): Observable<DateHistogramBucket[]> {
    return this.api.request((client, signal) =>
      client.GET('/serps/date-histogram', {
        params: { query: { ...filterParams, interval } },
        signal,
      }),
    );
  }

  /**
   * Get the unbranded view of a SERP, loading its organic results by the SERP's references.
   */
  getUnbrandedSerp(serp: SearchResult): Observable<UnbrandedSerp> {
    const references = serp.warc_organic_results ?? [];
    const organicResults$ = references.length
      ? this.getOrganicResults(references.map(reference => reference.id))
      : of([] as OrganicResult[]);
    return organicResults$.pipe(map(organicResults => unbrandSerp(serp, organicResults)));
  }

  /**
   * Get organic results by their IDs (e.g., as referenced by a SERP).
   */
  getOrganicResults(ids: string[]): Observable<OrganicResult[]> {
    return this.api.request((client, signal) =>
      client.GET('/organic-results/', { params: { query: { ids } }, signal }),
    );
  }

  getSerp(serpId: string): Observable<SearchResult | null> {
    return this.api.request((client, signal) =>
      client.GET('/serps/{id}', { params: { path: { id: serpId } }, signal }),
    );
  }

  /**
   * Get related SERPs, i.e., other SERPs with the same query.
   */
  getRelatedSerps(serp: SearchResult, size = 10, sameProvider = false): Observable<SearchResult[]> {
    return this.api.request((client, signal) =>
      client.GET('/serps/', {
        params: {
          query: {
            query: serp.url_query,
            exclude_id: serp._id,
            provider_id: sameProvider ? serp.provider.id : undefined,
            size,
          },
        },
        signal,
      }),
    );
  }

  /**
   * Get SERP details, including related SERPs and unfurled URL.
   */
  getSerpDetails(
    serp: SearchResult,
    options: { relatedSize?: number; sameProvider?: boolean } = {},
  ): Observable<SerpDetailsResponse> {
    return this.getRelatedSerps(serp, options.relatedSize, options.sameProvider).pipe(
      catchError(error => {
        console.warn('Failed to fetch related SERPs, showing empty list:', error);
        return of([] as SearchResult[]);
      }),
      map(related => ({
        serp_id: serp._id,
        serp,
        related,
        unfurl: unfurlUrl(serp.capture.url),
        unfurl_web: serp.unfurl_url,
      })),
    );
  }

  private buildFilterParams(query: string, options: SearchOptions): SerpFilterParams {
    const params: SerpFilterParams = { query };

    if (options.advancedMode !== undefined) {
      params.query_language = options.advancedMode;
    }
    if (options.fuzzy !== undefined) {
      params.fuzzy_matching = options.fuzzy;
    }
    if (options.fuzziness) {
      params.fuzziness = options.fuzziness;
    }
    if (options.expandSynonyms !== undefined) {
      params.expand_synonyms = options.expandSynonyms;
    }
    if (options.provider_id) {
      params.provider_id = options.provider_id;
    }
    if (options.year !== undefined) {
      params.from_timestamp = new Date(Date.UTC(options.year, 0, 1)).toISOString();
      params.to_timestamp = new Date(Date.UTC(options.year + 1, 0, 1)).toISOString();
    }
    if (options.status_code !== undefined) {
      params.status_code = options.status_code;
    }

    return params;
  }
}

/**
 * Convert date histogram buckets to (date, count) items, using the bucket's start date as its label.
 */
export function toHistogramItems(
  buckets: DateHistogramBucket[],
): { date: string; count: number }[] {
  return buckets.map(bucket => ({
    date: bucket.from_timestamp.split('T', 1)[0],
    count: bucket.count,
  }));
}

function unfurlUrl(url: string): UnfurlData | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  const queryParameters: Record<string, string | string[]> = {};
  for (const key of new Set(parsed.searchParams.keys())) {
    const values = parsed.searchParams.getAll(key);
    queryParameters[key] = values.length === 1 ? values[0] : values;
  }
  return {
    scheme: parsed.protocol.replace(/:$/, ''),
    netloc: parsed.hostname,
    port: parsed.port ? parseInt(parsed.port, 10) : null,
    path: parsed.pathname,
    path_segments: parsed.pathname.split('/').filter(segment => segment.length > 0),
    query_parameters: queryParameters,
    fragment: parsed.hash ? parsed.hash.substring(1) : null,
  };
}

function unbrandSerp(serp: SearchResult, organicResults: OrganicResult[]): UnbrandedSerp {
  return {
    serp_id: serp._id,
    query: {
      raw: serp.url_query,
      parsed: serp.url_query,
    },
    results: organicResults
      .map(result => ({
        position: result.rank,
        url: result.url,
        title: result.title,
        snippet: result.text,
      }))
      .sort((a, b) => a.position - b.position),
    metadata: {
      timestamp: serp.capture.timestamp,
      url: serp.capture.url,
      status_code: serp.capture.status_code,
    },
  };
}
