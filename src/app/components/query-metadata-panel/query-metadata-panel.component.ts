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
import { CommonModule } from '@angular/common';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import {
  AqlButtonComponent,
  AqlTabMenuComponent,
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
import { MetadataHtmlTabComponent } from './metadata-html-tab/metadata-html-tab.component';
import { MetadataWebsiteTabComponent } from './metadata-website-tab/metadata-website-tab.component';
import { MetadataInfoTabComponent } from './metadata-info-tab/metadata-info-tab.component';
import { MetadataRelatedTabComponent } from './metadata-related-tab/metadata-related-tab.component';
import { MetadataUnfurlTabComponent } from './metadata-unfurl-tab/metadata-unfurl-tab.component';
import { ProviderDetail } from '../../services/provider.service';
import { ArchiveDetail } from '../../models/archive.model';
import { MetadataProviderTabComponent } from './metadata-provider-tab/metadata-provider-tab.component';
import { MetadataArchiveTabComponent } from './metadata-archive-tab/metadata-archive-tab.component';
import { MetadataStatisticsTabComponent } from './metadata-statistics-tab/metadata-statistics-tab.component';

@Component({
  selector: 'app-query-metadata-panel',
  standalone: true,
  imports: [
    CommonModule,
    TranslateModule,
    AqlButtonComponent,
    AqlTabMenuComponent,
    AqlTooltipDirective,
    MetadataHtmlTabComponent,
    MetadataWebsiteTabComponent,
    MetadataInfoTabComponent,
    MetadataRelatedTabComponent,
    MetadataUnfurlTabComponent,
    MetadataProviderTabComponent,
    MetadataArchiveTabComponent,
    MetadataStatisticsTabComponent,
  ],
  templateUrl: './query-metadata-panel.component.html',
  styleUrl: './query-metadata-panel.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppQueryMetadataPanelComponent {
  readonly isOpen = input.required<boolean>();
  readonly searchResult = input<SearchResult | null>(null);
  readonly providerDetail = input<ProviderDetail | null>(null);
  readonly archiveDetail = input<ArchiveDetail | null>(null);
  readonly isLoading = input<boolean>(false);
  readonly error = input<string | null>(null);
  readonly closePanel = output<void>();
  readonly relatedSerpSelected = output<SearchResult>();
  readonly activeTab = signal<string>('html');
  readonly originalResult = signal<SearchResult | null>(null);
  readonly history = signal<SearchResult[]>([]);
  readonly tabs = signal<TabItem[]>([]);
  readonly serpDetails = signal<SerpDetailsResponse | null>(null);
  readonly isLoadingDetails = signal<boolean>(false);
  readonly detailsError = signal<string | null>(null);
  readonly hasContent = computed(() => {
    return (
      this.searchResult() !== null ||
      this.providerDetail() !== null ||
      this.archiveDetail() !== null
    );
  });
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

    return [
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
    ].join(' ');
  });
  readonly contentWrapperClasses = computed(() => {
    const isSidebarCollapsed = this.sessionService.sidebarCollapsed();
    return isSidebarCollapsed ? 'w-[60vw]' : 'w-[calc(60vw-20rem)]';
  });

  private readonly sessionService = inject(SessionService);
  private readonly translate = inject(TranslateService);
  private readonly searchService = inject(SearchService);
  private isInternalNavigation = false;
  private lastLoadedSerpId = '';

  constructor() {
    effect(() => {
      this.searchResult();
      this.providerDetail();
      this.archiveDetail();
      this.updateTabLabels();
    });

    this.translate
      .get('metadata.htmlView')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        this.updateTabLabels();
      });

    this.translate.onLangChange.pipe(takeUntilDestroyed()).subscribe(() => {
      this.updateTabLabels();
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
  }

  onRelatedSerpClick(searchResult: SearchResult): void {
    if (!this.originalResult()) {
      this.originalResult.set(this.searchResult());
    }

    // Add current search result to history
    const current = this.searchResult();
    if (current) {
      this.history.update(h => [...h, current]);
    }

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

  private updateTabLabels(): void {
    const result = this.searchResult();
    const provider = this.providerDetail();
    const archive = this.archiveDetail();

    if (result) {
      if (this.activeTab() === 'provider-info' || this.activeTab() === 'archive-info') {
        this.activeTab.set('html');
      }
      this.tabs.set([
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
    } else if (provider) {
      this.activeTab.set(this.activeTab() === 'statistics' ? 'statistics' : 'provider-info');
      this.tabs.set([
        {
          id: 'provider-info',
          label: this.translate.instant('providers.details'),
          icon: 'bi-info-circle',
        },
        {
          id: 'statistics',
          label: this.translate.instant('statistics.title'),
          icon: 'bi-bar-chart',
        },
      ]);
    } else if (archive) {
      this.activeTab.set(this.activeTab() === 'statistics' ? 'statistics' : 'archive-info');
      this.tabs.set([
        {
          id: 'archive-info',
          label: this.translate.instant('archives.details'),
          icon: 'bi-info-circle',
        },
        {
          id: 'statistics',
          label: this.translate.instant('statistics.title'),
          icon: 'bi-bar-chart',
        },
      ]);
    } else {
      this.tabs.set([]);
    }
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
