import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_CONFIG } from '../config/api.config';
import {
  SearchResponse,
  SearchParams,
  QueryMetadataResponse,
  QueryMetadataParams,
  SerpDetailsResponse,
} from '../models/search.model';

@Injectable({
  providedIn: 'root',
})
export class SearchService {
  private readonly apiService = inject(ApiService);

  search(query: string, size?: number, offset?: number): Observable<SearchResponse> {
    const params: Record<string, string | number> = {
      query: query,
    };

    if (size !== undefined) {
      params['page_size'] = size;
    }
    if (offset !== undefined) {
      params['offset'] = offset;
    }

    return this.apiService.get<SearchResponse>(API_CONFIG.endpoints.serps, params);
  }

  searchWithParams(params: SearchParams): Observable<SearchResponse> {
    const apiParams: Record<string, string | number> = {
      query: params.query,
    };

    if (params.size !== undefined) {
      apiParams['page_size'] = params.size;
    }
    if (params.provider_id) {
      apiParams['provider_id'] = params.provider_id;
    }
    if (params.year !== undefined) {
      apiParams['year'] = params.year;
    }
    if (params.status_code !== undefined) {
      apiParams['status_code'] = params.status_code;
    }

    return this.apiService.get<SearchResponse>(API_CONFIG.endpoints.serps, apiParams);
  }

  getQueryMetadata(params: QueryMetadataParams): Observable<QueryMetadataResponse> {
    const apiParams: Record<string, string | number> = {
      query: params.query,
    };

    if (params.top_n_queries !== undefined) {
      apiParams['top_n_queries'] = params.top_n_queries;
    }
    if (params.interval) {
      apiParams['interval'] = params.interval;
    }
    if (params.top_providers !== undefined) {
      apiParams['top_providers'] = params.top_providers;
    }
    if (params.top_archives !== undefined) {
      apiParams['top_archives'] = params.top_archives;
    }
    if (params.last_n_months !== undefined) {
      apiParams['last_n_months'] = params.last_n_months;
    }
    if (params.provider_id) {
      apiParams['provider_id'] = params.provider_id;
    }

    return this.apiService.get<QueryMetadataResponse>(API_CONFIG.endpoints.serpsPreview, apiParams);
  }

  /**
   * Get SERP details by ID with optional additional fields.
   * @param serpId The SERP document ID
   * @param includeFields Array of fields to include: 'original_url', 'memento_url', 'related', 'unfurl', 'direct_links', 'unbranded'
   * @param options Additional options for the request
   */
  getSerpDetails(
    serpId: string,
    includeFields: string[] = [],
    options: {
      removeTracking?: boolean;
      relatedSize?: number;
      sameProvider?: boolean;
    } = {},
  ): Observable<SerpDetailsResponse> {
    const params: Record<string, string | number | boolean> = {};

    if (includeFields.length > 0) {
      params['include'] = includeFields.join(',');
    }

    if (options.removeTracking !== undefined) {
      params['remove_tracking'] = options.removeTracking;
    }

    if (options.relatedSize !== undefined) {
      params['related_size'] = options.relatedSize;
    }

    if (options.sameProvider !== undefined) {
      params['same_provider'] = options.sameProvider;
    }

    return this.apiService.get<SerpDetailsResponse>(API_CONFIG.endpoints.serp(serpId), params);
  }
}
