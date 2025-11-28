import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../config/api.config';

// Central service class for all HTTP requests
@Injectable({
  providedIn: 'root',
})
export class ApiService {
  private readonly http = inject(HttpClient);

  get<T>(endpoint: string, params?: Record<string, string | number | boolean>): Observable<T> {
    const url = this.buildUrl(endpoint);
    const httpParams = this.buildParams(params);

    return this.http.get<T>(url, { params: httpParams });
  }

  post<T>(endpoint: string, body: unknown): Observable<T> {
    const url = this.buildUrl(endpoint);
    return this.http.post<T>(url, body);
  }

  put<T>(endpoint: string, body: unknown): Observable<T> {
    const url = this.buildUrl(endpoint);
    return this.http.put<T>(url, body);
  }

  patch<T>(endpoint: string, body: unknown): Observable<T> {
    const url = this.buildUrl(endpoint);
    return this.http.patch<T>(url, body);
  }

  delete<T>(endpoint: string): Observable<T> {
    const url = this.buildUrl(endpoint);
    return this.http.delete<T>(url);
  }

  private buildUrl(endpoint: string): string {
    if (endpoint.startsWith('http')) {
      return endpoint;
    }

    const cleanEndpoint = endpoint.startsWith('/') ? endpoint.substring(1) : endpoint;
    const baseUrl = API_CONFIG.baseUrl.endsWith('/')
      ? API_CONFIG.baseUrl.slice(0, -1)
      : API_CONFIG.baseUrl;

    return `${baseUrl}/${cleanEndpoint}`;
  }

  private buildParams(params?: Record<string, string | number | boolean>): HttpParams {
    let httpParams = new HttpParams();

    if (params) {
      Object.keys(params).forEach(key => {
        const value = params[key];
        if (value !== null && value !== undefined) {
          httpParams = httpParams.set(key, String(value));
        }
      });
    }

    return httpParams;
  }
}
