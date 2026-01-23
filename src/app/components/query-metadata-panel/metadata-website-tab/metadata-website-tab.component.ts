import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { SearchResult } from '../../../models/search.model';

@Component({
  selector: 'app-metadata-website-tab',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './metadata-website-tab.component.html',
  styleUrl: './metadata-website-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataWebsiteTabComponent {
  readonly searchResult = input<SearchResult | null>(null);
  readonly isActive = input<boolean>(false);
  readonly isIframeLoading = signal<boolean>(false);
  readonly iframeError = signal<boolean>(false);
  readonly archiveDate = computed<string>(() => {
    const result = this.searchResult();
    if (!result) return '';

    const timestamp = result._source.capture.timestamp;
    if (!timestamp) return '';

    try {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) return '';

      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short',
      });
    } catch {
      return '';
    }
  });
  readonly mementoUrlString = computed<string>(() => {
    const result = this.searchResult();
    if (!result) return '';

    const mementoApiUrl = result._source.archive?.memento_api_url;
    const timestamp = result._source.capture.timestamp;
    const captureUrl = result._source.capture.url;

    if (!mementoApiUrl || !timestamp || !captureUrl) {
      return captureUrl || '';
    }

    const formattedTimestamp = this.formatTimestampForMemento(timestamp);
    return `${mementoApiUrl}/${formattedTimestamp}/${captureUrl}`;
  });
  readonly mementoUrl = computed<SafeResourceUrl | null>(() => {
    const urlString = this.mementoUrlString();
    if (!urlString) return null;
    return this.sanitizer.bypassSecurityTrustResourceUrl(urlString);
  });
  readonly archiveName = computed<string>(() => {
    const result = this.searchResult();
    if (!result) return '';

    const mementoApiUrl = result._source.archive?.memento_api_url;
    if (!mementoApiUrl) return 'Unknown Archive';

    const knownArchives: Record<string, string> = {
      'https://web.archive.org/web': 'Internet Archive (Wayback Machine)',
      'https://web.archive.org': 'Internet Archive (Wayback Machine)',
      'https://archive.org': 'Internet Archive',
    };

    if (knownArchives[mementoApiUrl]) {
      return knownArchives[mementoApiUrl];
    }

    try {
      const url = new URL(mementoApiUrl);
      const domain = url.host || url.pathname;
      const name = domain.replace(/-/g, ' ').replace(/\.org/g, '').trim();
      return name ? name.replace(/\b\w/g, c => c.toUpperCase()) : 'Unknown Archive';
    } catch {
      return 'Unknown Archive';
    }
  });
  readonly archiveHomepage = computed<string | null>(() => {
    const result = this.searchResult();
    if (!result) return null;

    const mementoApiUrl = result._source.archive?.memento_api_url;
    if (!mementoApiUrl) return null;

    if (mementoApiUrl.startsWith('https://web.archive.org')) {
      return 'https://web.archive.org';
    }

    try {
      const url = new URL(mementoApiUrl);
      return `${url.protocol}//${url.host}`;
    } catch {
      return null;
    }
  });
  readonly cdxApiUrl = computed<string | null>(() => {
    const result = this.searchResult();
    return result?._source.archive?.cdx_api_url || null;
  });

  private readonly sanitizer = inject(DomSanitizer);
  private lastLoadedUrl = '';

  constructor() {
    effect(() => {
      const url = this.mementoUrlString();
      if (url && this.isActive() && url !== this.lastLoadedUrl) {
        this.lastLoadedUrl = url;
        this.isIframeLoading.set(true);
        this.iframeError.set(false);
      }
    });
  }

  onIframeLoad(): void {
    this.isIframeLoading.set(false);
    this.iframeError.set(false);
  }

  onIframeError(): void {
    this.isIframeLoading.set(false);
    this.iframeError.set(true);
  }

  private formatTimestampForMemento(isoTimestamp: string): string {
    try {
      const date = new Date(isoTimestamp);
      if (isNaN(date.getTime())) {
        return '';
      }

      const year = date.getUTCFullYear();
      const month = String(date.getUTCMonth() + 1).padStart(2, '0');
      const day = String(date.getUTCDate()).padStart(2, '0');
      const hours = String(date.getUTCHours()).padStart(2, '0');
      const minutes = String(date.getUTCMinutes()).padStart(2, '0');
      const seconds = String(date.getUTCSeconds()).padStart(2, '0');

      return `${year}${month}${day}${hours}${minutes}${seconds}`;
    } catch {
      return '';
    }
  }
}
