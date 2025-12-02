import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_CONFIG } from '../config/api.config';
import { SearchResponse, SearchParams } from '../models/search.model';

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
      params['size'] = size;
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
      apiParams['size'] = params.size;
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
}
