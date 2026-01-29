import { Injectable, inject } from '@angular/core';
import { Observable, catchError, map, of, shareReplay } from 'rxjs';
import { ApiService } from './api.service';
import { API_CONFIG } from '../config/api.config';
import { ArchivesApiResponse, ArchiveDetail, ArchiveDetailResponse } from '../models/archive.model';
import { ArchiveStatistics } from '../models/statistics.model';

@Injectable({
  providedIn: 'root',
})
export class ArchiveService {
  private readonly apiService = inject(ApiService);
  private archivesCache$?: Observable<ArchiveDetail[]>;

  /**
   * Fetch all available archives from the backend.
   * Results are cached to avoid redundant API calls.
   */
  getArchives(): Observable<ArchiveDetail[]> {
    if (!this.archivesCache$) {
      this.archivesCache$ = this.apiService
        .get<ArchivesApiResponse>(API_CONFIG.endpoints.archives)
        .pipe(
          map(response =>
            response.archives.map(archive => ({
              id: archive.id,
              name: archive.name,
              cdx_api_url: archive.cdx_api_url,
              serp_count: archive.serp_count,
            })),
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
    return this.apiService.get<ArchiveDetailResponse>(API_CONFIG.endpoints.archive(archiveId)).pipe(
      map(response => ({
        id: response.archive.id,
        name: response.archive.name,
        cdx_api_url: response.archive.cdx_api_url,
        memento_api_url: response.archive.memento_api_url,
      })),
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
   * Fetch statistics for a specific archive.
   */
  getArchiveStatistics(archiveId: string): Observable<ArchiveStatistics> {
    return this.apiService.get<ArchiveStatistics>(
      API_CONFIG.endpoints.archiveStatistics(encodeURIComponent(archiveId)),
    );
  }
}
