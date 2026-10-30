import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import createClient, { Client } from 'openapi-fetch';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../config/api.config';
import { paths } from './schema';

/**
 * Typed client for the AQL API (generated from its OpenAPI specification, see `npm run generate-api`).
 *
 * Requests are sent via Angular's `HttpClient`, so that HTTP interceptors and testing utilities apply.
 */
@Injectable({
  providedIn: 'root',
})
export class AqlApiClient {
  readonly client: Client<paths>;

  private readonly http = inject(HttpClient);

  constructor() {
    this.client = createClient<paths>({
      baseUrl: API_CONFIG.baseUrl.replace(/\/$/, ''),
      fetch: request => this.fetch(request),
    });
  }

  /**
   * Wrap a typed API request as a (cold and cancellable) observable that emits the response data or errors with an `HttpErrorResponse`.
   */
  request<T>(
    send: (
      client: Client<paths>,
      signal: AbortSignal,
    ) => Promise<{ data?: T; error?: unknown; response: Response }>,
  ): Observable<T> {
    return new Observable<T>(subscriber => {
      const controller = new AbortController();
      send(this.client, controller.signal).then(
        ({ data, error, response }) => {
          if (error !== undefined || !response.ok) {
            subscriber.error(
              new HttpErrorResponse({
                error,
                status: response.status,
                statusText: response.statusText,
                url: response.url,
              }),
            );
            return;
          }
          subscriber.next(data as T);
          subscriber.complete();
        },
        error => {
          if (!controller.signal.aborted) {
            subscriber.error(error);
          }
        },
      );
      return () => controller.abort();
    });
  }

  private async fetch(request: Request): Promise<Response> {
    // Only await the body if there is one, so that requests without a body are sent synchronously.
    const body = request.body ? await request.text() : null;
    return new Promise<Response>((resolve, reject) => {
      const headers = new HttpHeaders(Object.fromEntries(request.headers.entries()));
      const subscription = this.http
        .request(request.method, request.url, {
          body,
          headers,
          observe: 'response',
          responseType: 'text',
        })
        .subscribe({
          next: response =>
            resolve(
              new Response(response.body, {
                status: response.status,
                statusText: response.statusText,
                headers: headersToRecord(response.headers),
              }),
            ),
          error: (error: unknown) => {
            // Pass HTTP error responses on to openapi-fetch (but not network errors).
            if (error instanceof HttpErrorResponse && error.status !== 0) {
              resolve(
                new Response(
                  typeof error.error === 'string' ? error.error : JSON.stringify(error.error),
                  {
                    status: error.status,
                    statusText: error.statusText,
                    headers: headersToRecord(error.headers),
                  },
                ),
              );
            } else {
              reject(error);
            }
          },
        });
      request.signal.addEventListener('abort', () => {
        subscription.unsubscribe();
        reject(request.signal.reason);
      });
    });
  }
}

function headersToRecord(headers: HttpHeaders): Record<string, string> {
  return Object.fromEntries(headers.keys().map(key => [key, headers.get(key) ?? '']));
}
