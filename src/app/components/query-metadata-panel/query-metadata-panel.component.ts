import {
  Component,
  input,
  output,
  signal,
  computed,
  effect,
  ChangeDetectionStrategy,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import {
  AqlButtonComponent,
  AqlTabMenuComponent,
  AqlPanelComponent,
  AqlTooltipDirective,
  TabItem,
} from 'aql-stylings';
import {
  SearchResult,
  SerpDetailsResponse,
  RelatedSerp,
  UnfurlData,
} from '../../models/search.model';
import { SessionService } from '../../services/session.service';
import { SearchService } from '../../services/search.service';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-query-metadata-panel',
  standalone: true,
  imports: [
    CommonModule,
    TranslateModule,
    AqlButtonComponent,
    AqlTabMenuComponent,
    AqlPanelComponent,
    AqlTooltipDirective,
  ],
  templateUrl: './query-metadata-panel.component.html',
  styleUrl: './query-metadata-panel.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppQueryMetadataPanelComponent {
  readonly isOpen = input.required<boolean>();
  readonly searchResult = input<SearchResult | null>(null);
  readonly closePanel = output<void>();
  readonly relatedSerpSelected = output<SearchResult>();
  readonly activeTab = signal<string>('text');
  readonly isIframeLoading = signal<boolean>(false);
  readonly iframeError = signal<boolean>(false);
  readonly originalResult = signal<SearchResult | null>(null);
  readonly history = signal<SearchResult[]>([]);
  readonly tabs = signal<TabItem[]>([]);
  readonly serpDetails = signal<SerpDetailsResponse | null>(null);
  readonly isLoadingDetails = signal<boolean>(false);
  readonly detailsError = signal<string | null>(null);
  readonly relatedSerps = computed<RelatedSerp[]>(() => {
    const details = this.serpDetails();
    return details?.related?.serps || [];
  });
  readonly unfurlData = computed<UnfurlData | null>(() => {
    const details = this.serpDetails();
    return details?.unfurl || null;
  });
  readonly unfurlWebUrl = computed<string | null>(() => {
    const details = this.serpDetails();
    return details?.unfurl_web || null;
  });
  readonly isViewingRelatedSerp = computed<boolean>(() => {
    const original = this.originalResult();
    const current = this.searchResult();
    return original !== null && current !== null && original._id !== current._id;
  });
  readonly panelClasses = computed(() => {
    const isSidebarCollapsed = this.sessionService.sidebarCollapsed();
    const isOpen = this.isOpen();

    const widthClass = isOpen ? (isSidebarCollapsed ? 'w-[60vw]' : 'w-[calc(60vw-20rem)]') : 'w-0';

    const classes = [
      'h-full',
      widthClass,
      'bg-base-100',
      'border-l',
      'border-base-300',
      'flex',
      'flex-col',
      'flex-shrink-0',
      'transition-[width]',
      'duration-300',
      'ease-in-out',
      'overflow-hidden',
    ];

    return classes.join(' ');
  });
  readonly contentWrapperClasses = computed(() => {
    const isSidebarCollapsed = this.sessionService.sidebarCollapsed();
    return isSidebarCollapsed ? 'w-[60vw]' : 'w-[calc(60vw-20rem)]';
  });
  /**
   * Computed raw memento URL string for use in links
   */
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
  /**
   * Derive human-readable archive name from the Memento API URL
   */
  readonly archiveName = computed<string>(() => {
    const result = this.searchResult();
    if (!result) return '';

    const mementoApiUrl = result._source.archive?.memento_api_url;
    if (!mementoApiUrl) return 'Unknown Archive';

    // Known archives mapping
    const knownArchives: Record<string, string> = {
      'https://web.archive.org/web': 'Internet Archive (Wayback Machine)',
      'https://web.archive.org': 'Internet Archive (Wayback Machine)',
      'https://archive.org': 'Internet Archive',
    };

    if (knownArchives[mementoApiUrl]) {
      return knownArchives[mementoApiUrl];
    }

    // Generic fallback: extract domain from URL (mirror backend behavior)
    try {
      const url = new URL(mementoApiUrl);
      const domain = url.host || url.pathname;
      const name = domain.replace(/-/g, ' ').replace(/\.org/g, '').trim();
      return name ? name.replace(/\b\w/g, c => c.toUpperCase()) : 'Unknown Archive';
    } catch {
      return 'Unknown Archive';
    }
  });
  /**
   * Derive archive homepage URL from the Memento API URL
   */
  readonly archiveHomepage = computed<string | null>(() => {
    const result = this.searchResult();
    if (!result) return null;

    const mementoApiUrl = result._source.archive?.memento_api_url;
    if (!mementoApiUrl) return null;

    // Known homepages
    if (mementoApiUrl.startsWith('https://web.archive.org')) {
      return 'https://web.archive.org';
    }

    // Generic: return base URL without /web or other path components (mirror backend behavior)
    try {
      const url = new URL(mementoApiUrl);
      return `${url.protocol}//${url.host}`;
    } catch {
      return null;
    }
  });
  /**
   * Get CDX API URL from archive data
   */
  readonly cdxApiUrl = computed<string | null>(() => {
    const result = this.searchResult();
    return result?._source.archive?.cdx_api_url || null;
  });

  private readonly sessionService = inject(SessionService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly translate = inject(TranslateService);
  private readonly searchService = inject(SearchService);
  private readonly languageService = inject(LanguageService);
  private isInternalNavigation = false;
  private lastLoadedUrl = '';
  private lastLoadedSerpId = '';

  constructor() {
    // Wait for translations to load before updating labels
    this.translate
      .get('metadata.textView')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        this.updateTabLabels();
      });

    this.translate.onLangChange.pipe(takeUntilDestroyed()).subscribe(() => {
      this.updateTabLabels();
    });

    // load iframe for website tab
    effect(() => {
      const url = this.mementoUrlString();
      if (url && this.activeTab() === 'website' && url !== this.lastLoadedUrl) {
        this.lastLoadedUrl = url;
        this.isIframeLoading.set(true);
        this.iframeError.set(false);
      }
    });

    // fetch SERP details
    effect(() => {
      const result = this.searchResult();
      if (result && result._id !== this.lastLoadedSerpId) {
        if (this.isInternalNavigation) {
          this.isInternalNavigation = false;
        } else {
          this.originalResult.set(null);
          this.history.set([]);
        }

        this.lastLoadedSerpId = result._id;
        this.fetchSerpDetails(result._id);
      } else if (!result) {
        this.serpDetails.set(null);
        this.lastLoadedSerpId = '';
        this.originalResult.set(null);
        this.history.set([]);
      }
    });
  }

  onClose(): void {
    this.originalResult.set(null);
    this.closePanel.emit();
  }

  onTabChange(tabId: string): void {
    this.activeTab.set(tabId);
    // Reset iframe state
    if (tabId === 'website') {
      this.isIframeLoading.set(true);
      this.iframeError.set(false);
    }
  }

  onIframeLoad(): void {
    this.isIframeLoading.set(false);
    this.iframeError.set(false);
  }

  onIframeError(): void {
    this.isIframeLoading.set(false);
    this.iframeError.set(true);
  }

  /**
   * Formats an ISO timestamp to the memento format (YYYYMMDDHHmmss)
   * @param isoTimestamp ISO 8601 timestamp string
   * @returns Formatted timestamp string for memento URL
   */
  formatTimestampForMemento(isoTimestamp: string): string {
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

  getExtractionText(): string {
    // Placeholder - will be replaced with actual extraction data
    return 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus lacinia odio vitae vestibulum vestibulum. Cras venenatis euismod malesuada. Nullam ac odio tempor orci dapibus ultrices in iaculis nunc.';
  }

  onRelatedSerpClick(serp: RelatedSerp): void {
    if (!this.originalResult()) {
      this.originalResult.set(this.searchResult());
    }

    // Add current search result to history
    const current = this.searchResult();
    if (current) {
      this.history.update(h => [...h, current]);
    }

    const searchResult: SearchResult = {
      _index: '',
      _type: '',
      _id: serp._id,
      _score: serp._score,
      _source: serp._source,
    };

    this.isInternalNavigation = true;
    this.relatedSerpSelected.emit(searchResult);
  }

  // Navigate back one item in history
  onBackOne(): void {
    const historyStack = this.history();
    if (historyStack.length === 0) return;

    const previous = historyStack[historyStack.length - 1];
    this.history.update(h => h.slice(0, -1));

    this.isInternalNavigation = true;
    this.relatedSerpSelected.emit(previous);
  }

  // Navigate back to the original search result
  onBackToOriginal(): void {
    const original = this.originalResult();
    if (original) {
      this.history.set([]);
      this.isInternalNavigation = true;
      this.relatedSerpSelected.emit(original);
      this.originalResult.set(null);
    }
  }

  getQueryParamEntries(): { key: string; value: string }[] {
    const unfurl = this.unfurlData();
    if (!unfurl?.query_parameters) return [];

    return Object.entries(unfurl.query_parameters).map(([key, value]) => ({
      key,
      value: Array.isArray(value) ? value.join(', ') : value,
    }));
  }

  formatDate(dateString: string): string {
    return this.languageService.formatDate(dateString);
  }

  private updateTabLabels(): void {
    this.tabs.set([
      {
        id: 'text',
        label: this.translate.instant('metadata.textView'),
        icon: 'bi-file-text',
      },
      {
        id: 'html',
        label: this.translate.instant('metadata.htmlView'),
        icon: 'bi-code-square',
      },
      {
        id: 'website',
        label: this.translate.instant('metadata.websiteTab'),
        icon: 'bi-globe',
      },
      {
        id: 'metadata',
        label: this.translate.instant('metadata.metadata'),
        icon: 'bi-info-circle',
      },
      {
        id: 'related',
        label: this.translate.instant('metadata.relatedSerps'),
        icon: 'bi-search',
      },
      {
        id: 'unfurl',
        label: this.translate.instant('metadata.urlDetails'),
        icon: 'bi-link-45deg',
      },
    ]);
  }

  private fetchSerpDetails(serpId: string): void {
    this.isLoadingDetails.set(true);
    this.detailsError.set(null);
    this.serpDetails.set(null);

    let completedRequests = 0;
    const totalRequests = 2;
    const partialResponse: Partial<SerpDetailsResponse> = {
      serp_id: serpId,
    };

    const checkComplete = () => {
      completedRequests++;
      if (completedRequests >= totalRequests) {
        this.serpDetails.set(partialResponse as SerpDetailsResponse);
        this.isLoadingDetails.set(false);
      }
    };

    this.searchService.getSerpDetails(serpId, ['unfurl']).subscribe({
      next: response => {
        partialResponse.unfurl = response.unfurl;
        partialResponse.unfurl_web = response.unfurl_web;
        partialResponse.serp = response.serp;
        checkComplete();
      },
      error: err => {
        console.warn('Failed to fetch unfurl data:', err);
        checkComplete();
      },
    });

    this.searchService.getSerpDetails(serpId, ['related'], { relatedSize: 10 }).subscribe({
      next: response => {
        partialResponse.related = response.related;
        checkComplete();
      },
      error: err => {
        console.warn('Failed to fetch related SERPs (backend issue), showing empty list:', err);
        partialResponse.related = { count: 0, serps: [] };
        checkComplete();
      },
    });
  }
}
