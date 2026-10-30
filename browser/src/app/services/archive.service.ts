import { Injectable, inject } from '@angular/core';
import { Observable, catchError, forkJoin, map, of, shareReplay, switchMap } from 'rxjs';
import { AqlApiClient } from '../api/client';
import { ArchiveResponse, ArchiveDetail } from '../models/archive.model';
import { ArchiveStatistics } from '../models/statistics.model';
import { SearchService, SerpFilterParams, toHistogramItems } from './search.service';

/**
 * Maximum number of archives to fetch at once (Elasticsearch's default result window).
 */
const MAX_ARCHIVES = 10000;

function toArchiveDetail(archive: ArchiveResponse): ArchiveDetail {
  return {
    id: archive._id,
    name: archive.name,
    cdx_api_url: archive.cdx_api_url,
    memento_api_url: archive.memento_api_url,
    homepage: archive.homepage ?? undefined,
  };
}

@Injectable({
  providedIn: 'root',
})
export class ArchiveService {
  private readonly api = inject(AqlApiClient);
  private readonly searchService = inject(SearchService);
  private archivesCache$?: Observable<ArchiveDetail[]>;

  /**
   * Fetch all available archives from the backend.
   * Results are cached to avoid redundant API calls.
   */
  getArchives(): Observable<ArchiveDetail[]> {
    if (!this.archivesCache$) {
      this.archivesCache$ = this.api
        .request((client, signal) =>
          client.GET('/archives/', { params: { query: { size: MAX_ARCHIVES } }, signal }),
        )
        .pipe(
          map(response => response.map(toArchiveDetail)),
          switchMap(archives =>
            archives.length
              ? forkJoin(archives.map(archive => this.withSerpCount(archive)))
              : of([]),
          ),
          map(archives => archives.sort((a, b) => a.name.localeCompare(b.name))),
          shareReplay(1),
          catchError(error => {
            console.error('Failed to fetch archives:', error);
            this.archivesCache$ = undefined;
            return of([]);
          }),
        );
    }
    return this.archivesCache$;
  }

  /**
   * Clear the archives cache to force a fresh fetch on next call.
   */
  clearCache(): void {
    this.archivesCache$ = undefined;
  }

  /**
   * Fetch a specific archive by ID from the backend.
   */
  getArchiveById(archiveId: string): Observable<ArchiveDetail | null> {
    return this.api
      .request((client, signal) =>
        client.GET('/archives/{id}', { params: { path: { id: archiveId } }, signal }),
      )
      .pipe(
        map(data => {
          if (!data) {
            throw new Error('Archive data not found in response');
          }
          return toArchiveDetail(data);
        }),
        switchMap(archive => this.withSerpCount(archive)),
        catchError(error => {
          console.error(`Failed to fetch archive ${archiveId}:`, error);
          return of(null);
        }),
      );
  }

  /**
   * Search archives by query string.
   */
  searchArchives(query: string): Observable<ArchiveDetail[]> {
    return this.getArchives().pipe(
      map(archives => {
        if (!query.trim()) return archives;
        const lowerQuery = query.toLowerCase();
        return archives.filter(archive => archive.name.toLowerCase().includes(lowerQuery));
      }),
    );
  }

  /**
   * Fetch statistics for a specific archive, aggregated from the archive's SERPs.
   */
  getArchiveStatistics(archiveId: string): Observable<ArchiveStatistics> {
    const filterParams: SerpFilterParams = { archive_id: archiveId };
    return forkJoin({
      serp_count: this.searchService.count(filterParams),
      unique_queries_count: this.searchService.countUnique(filterParams),
      top_providers: this.searchService.topProviders(filterParams, 5),
      date_histogram: this.searchService.dateHistogram(filterParams, 'month'),
    }).pipe(
      map(statistics => ({
        archive_id: archiveId,
        serp_count: statistics.serp_count,
        unique_queries_count: statistics.unique_queries_count,
        date_histogram: toHistogramItems(statistics.date_histogram),
        top_providers: statistics.top_providers.map(bucket => ({
          provider: bucket.provider._id,
          count: bucket.count,
        })),
      })),
    );
  }

  /**
   * Add the number of SERPs in the archive (if it can be counted).
   */
  private withSerpCount(archive: ArchiveDetail): Observable<ArchiveDetail> {
    return this.searchService.count({ archive_id: archive.id }).pipe(
      map(serp_count => ({ ...archive, serp_count })),
      catchError(() => of(archive)),
    );
  }
}
