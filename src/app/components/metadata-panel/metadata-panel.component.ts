import {
  Component,
  input,
  output,
  signal,
  computed,
  effect,
  ChangeDetectionStrategy,
  inject,
  OnInit,
} from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { AqlButtonComponent, AqlTabMenuComponent, TabItem } from 'aql-stylings';
import {
  SearchResult,
  SerpDetailsResponse,
  RelatedSerp,
  UnfurlData,
} from '../../models/search.model';
import { SessionService } from '../../services/session.service';
import { SearchService } from '../../services/search.service';
import { AppRelatedSerpCardComponent } from '../related-serp-card/related-serp-card.component';

@Component({
  selector: 'app-metadata-panel',
  standalone: true,
  imports: [
    CommonModule,
    TranslateModule,
    AqlButtonComponent,
    AqlTabMenuComponent,
    AppRelatedSerpCardComponent,
  ],
  templateUrl: './metadata-panel.component.html',
  styleUrl: './metadata-panel.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppMetadataPanelComponent implements OnInit {
  private readonly sessionService = inject(SessionService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly translate = inject(TranslateService);
  private readonly router = inject(Router);
  private readonly searchService = inject(SearchService);

  readonly isOpen = input.required<boolean>();
  readonly searchResult = input<SearchResult | null>(null);

  readonly closePanel = output<void>();
  readonly relatedSerpSelected = output<SearchResult>();

  readonly activeTab = signal<string>('text');
  readonly isIframeLoading = signal<boolean>(false);
  readonly iframeError = signal<boolean>(false);

  readonly tabs = signal<TabItem[]>([]);

  // SERP details data (fetched from API with include parameters)
  readonly serpDetails = signal<SerpDetailsResponse | null>(null);
  readonly isLoadingDetails = signal<boolean>(false);
  readonly detailsError = signal<string | null>(null);

  // Computed signals for related features
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

  ngOnInit(): void {
    // Wait for translations to be ready before setting tab labels
    this.translate.get('metadata.textView').subscribe(() => {
      this.updateTabLabels();
    });
    this.translate.onLangChange.subscribe(() => {
      this.updateTabLabels();
    });
  }

  private updateTabLabels(): void {
    this.tabs.set([
      { id: 'text', label: this.translate.instant('metadata.textView'), icon: 'bi-file-text' },
      { id: 'html', label: this.translate.instant('metadata.htmlView'), icon: 'bi-code-square' },
      { id: 'website', label: this.translate.instant('metadata.website'), icon: 'bi-globe' },
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

  private lastLoadedUrl = '';
  private lastLoadedSerpId = '';

  constructor() {
    // Effect to load iframe for website tab
    effect(() => {
      const url = this.mementoUrlString();
      if (url && this.activeTab() === 'website' && url !== this.lastLoadedUrl) {
        this.lastLoadedUrl = url;
        this.isIframeLoading.set(true);
        this.iframeError.set(false);
      }
    });

    // Effect to fetch SERP details when searchResult changes
    effect(() => {
      const result = this.searchResult();
      if (result && result._id !== this.lastLoadedSerpId) {
        this.lastLoadedSerpId = result._id;
        this.fetchSerpDetails(result._id);
      } else if (!result) {
        this.serpDetails.set(null);
        this.lastLoadedSerpId = '';
      }
    });
  }

  /**
   * Fetch SERP details - fetch each include separately to handle partial failures gracefully
   */
  private fetchSerpDetails(serpId: string): void {
    this.isLoadingDetails.set(true);
    this.detailsError.set(null);

    // Reset the details
    this.serpDetails.set(null);

    // Track completion of all requests
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

    // Fetch unfurl data
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

    // Fetch related SERPs
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

  readonly panelClasses = computed(() => {
    const isSidebarCollapsed = this.sessionService.sidebarCollapsed();
    const widthClass = isSidebarCollapsed ? 'w-[60vw]' : 'w-[calc(60vw-20rem)]';

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
    ];

    return classes.join(' ');
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

  /**
   * Computed memento URL - only recalculates when searchResult changes
   */
  readonly mementoUrl = computed<SafeResourceUrl | null>(() => {
    const urlString = this.mementoUrlString();
    if (!urlString) return null;
    return this.sanitizer.bypassSecurityTrustResourceUrl(urlString);
  });

  /**
   * Computed archive date for display - only recalculates when searchResult changes
   */
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

  onClose(): void {
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

  /**
   * Handle click on a related SERP card - loads the SERP details in the current panel
   */
  onRelatedSerpClick(serp: RelatedSerp): void {
    // Convert RelatedSerp to SearchResult format for the panel
    const searchResult: SearchResult = {
      _index: '',
      _type: '',
      _id: serp._id,
      _score: serp._score,
      _source: serp._source,
    };

    // Update the searchResult signal which will trigger the effect to fetch new details
    // We need to emit an event to update the parent component's selectedResult
    this.relatedSerpSelected.emit(searchResult);
  }

  /**
   * Get query parameter entries for display in unfurl view
   */
  getQueryParamEntries(): { key: string; value: string }[] {
    const unfurl = this.unfurlData();
    if (!unfurl?.query_parameters) return [];

    return Object.entries(unfurl.query_parameters).map(([key, value]) => ({
      key,
      value: Array.isArray(value) ? value.join(', ') : value,
    }));
  }

  /**
   * Format timestamp for display
   */
  formatTimestamp(timestamp: string): string {
    try {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) return timestamp;

      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return timestamp;
    }
  }
}
