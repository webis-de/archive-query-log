import {
  Component,
  inject,
  signal,
  effect,
  HostListener,
  ElementRef,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Location } from '@angular/common';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { AqlPaginationComponent, AqlButtonComponent } from 'aql-stylings';
import {
  createPanelNavigationController,
  PanelNavigationController,
} from '../../utils/panel-navigation';
import { SearchService } from '../../services/search.service';
import { SearchResult, QueryMetadataResponse } from '../../models/search.model';
import { SearchHistoryService } from '../../services/search-history.service';
import { SearchHeaderComponent } from '../../components/search-header/search-header.component';
import { FilterBadgeService } from '../../services/filter-badge.service';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';
import { ArchiveDetail } from '../../models/archive.model';
import { ProviderDetail } from '../../services/provider.service';
import { LanguageService } from '../../services/language.service';
import { FilterState } from '../../models/filter.model';
import { SearchFilter } from '../../models/project.model';
import { AppQueryMetadataPanelComponent } from '../../components/query-metadata-panel/query-metadata-panel.component';
import { QueryOverviewPanelComponent } from '../../components/query-overview-panel/query-overview-panel.component';
import { SessionService } from '../../services/session.service';
import { createSearchSuggestionsController } from '../../utils/search-suggestions';
import { createFilterBadgeController } from '../../utils/filter-badges';
import { SearchResultItemComponent } from '../../components/search-result-item/search-result-item.component';

@Component({
  selector: 'app-search-view',
  imports: [
    FormsModule,
    TranslateModule,
    SearchHeaderComponent,
    AqlPaginationComponent,
    AqlButtonComponent,
    AppQueryMetadataPanelComponent,
    QueryOverviewPanelComponent,
    SearchResultItemComponent
],
  templateUrl: './search-view.component.html',
  styleUrl: './search-view.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchViewComponent {
  readonly searchService = inject(SearchService);
  readonly searchHistoryService = inject(SearchHistoryService);
  readonly filterBadgeService = inject(FilterBadgeService);
  readonly suggestionsService = inject(SuggestionsService);
  readonly sessionService = inject(SessionService);
  readonly route = inject(ActivatedRoute);
  readonly router = inject(Router);
  readonly location = inject(Location);
  readonly translate = inject(TranslateService);
  readonly elementRef = inject(ElementRef);
  readonly destroyRef = inject(DestroyRef);
  readonly languageService = inject(LanguageService);
  readonly searchResults = signal<SearchResult[]>([]);
  readonly totalCount = signal<number>(0);
  readonly isLoading = signal<boolean>(false);
  readonly hasSearched = signal<boolean>(false);
  readonly metadataInterval = signal<'day' | 'week' | 'month'>('month');
  readonly metadataTopQueries = 10;
  readonly metadataTopProviders = 5;
  readonly metadataTopArchives = 5;
  readonly metadataLastMonths = 36;
  readonly metadataYear = signal<string | null>(null);
  readonly isPanelOpen = signal(false);
  readonly isTransitionEnabled = signal(false);
  readonly selectedResult = signal<SearchResult | null>(null);
  readonly isSidebarCollapsed = this.sessionService.sidebarCollapsed;
  readonly currentPage = signal<number>(1);
  readonly pageSize = signal<number>(10);
  readonly queryMetadata = signal<QueryMetadataResponse | null>(null);
  readonly isMetadataLoading = signal<boolean>(false);
  readonly didYouMeanSuggestions = signal<{ text: string; score: number; freq: number }[]>([]);
  readonly originalQuery = signal<string>('');
  readonly suggestions = this.suggestionsService.suggestionsWithMeta;
  readonly showSuggestions = signal<boolean>(false);
  searchQuery = '';
  currentSearchId?: string;
  isTemporarySearch = false;
  isLoadedFromHistory = false;
  isPaginationChange = false;
  activeFilters: string[] = ['All'];
  initialFilters: FilterState | null = null;

  private currentFilters: FilterState | null = null;
  private lastQueryString: string | null = null;
  private pendingSerpId: string | null = null;
  private readonly panelNavController: PanelNavigationController;
  private readonly suggestionsController = createSearchSuggestionsController({
    suggestionsService: this.suggestionsService,
    suggestions: this.suggestions,
    getQuery: () => this.searchQuery,
    setQuery: value => {
      this.searchQuery = value;
    },
    showSuggestions: this.showSuggestions,
    onSearch: () => this.onSearch(),
  });
  private readonly filterBadgeController = createFilterBadgeController({
    filterBadgeService: this.filterBadgeService,
    translate: this.translate,
    destroyRef: this.destroyRef,
    getFilters: () => this.currentFilters,
    setFilters: filters => {
      this.currentFilters = filters;
    },
    setBadges: badges => {
      this.activeFilters = badges;
    },
  });

  constructor() {
    this.panelNavController = createPanelNavigationController({
      location: this.location,
      basePath: '/serps',
      getSearchQuery: () => this.searchQuery,
      isPanelOpen: this.isPanelOpen,
    });

    this.filterBadgeController.refreshBadges();

    // Enable transitions after initial render to prevent animation on page load
    setTimeout(() => this.isTransitionEnabled.set(true), 50);

    effect(() => {
      const results = this.searchResults();
      const pendingId = this.pendingSerpId;

      if (pendingId && results.length > 0) {
        const result = results.find(r => r._id === pendingId);
        if (result && result._id !== this.selectedResult()?._id) {
          this.selectedResult.set(result);
          this.isPanelOpen.set(true);
          if (!this.sessionService.sidebarCollapsed()) {
            this.sessionService.setSidebarCollapsed(true);
          }
          this.pendingSerpId = null;
        }
      }
    });

    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe(queryParams => {
      const query = queryParams.get('q');
      const status = queryParams.get('status') || 'any';
      const provider = queryParams.get('provider') || undefined;
      const advancedMode = queryParams.get('advanced_mode') === 'true';
      const fuzzy = queryParams.get('fuzzy') === 'true';
      const fuzziness =
        (queryParams.get('fuzziness') as 'AUTO' | '0' | '1' | '2' | null) || undefined;
      const expandSynonyms = queryParams.get('expand_synonyms') === 'true';
      const year = queryParams.get('year') || '';
      const isTemp = queryParams.get('temp') === 'true';

      this.isTemporarySearch = isTemp;

      // Build current query string for comparison
      const currentQueryString = JSON.stringify({
        q: query,
        status,
        provider,
        advanced_mode: advancedMode,
        fuzzy,
        fuzziness,
        expandSynonyms,
        year,
      });

      // Update filters with new model (year-based, single provider)
      let newInitialFilters: FilterState | null = null;
      const yearNum = year ? parseInt(year, 10) : undefined;

      if (
        yearNum ||
        status !== 'any' ||
        provider ||
        advancedMode ||
        fuzzy ||
        fuzziness ||
        expandSynonyms
      ) {
        newInitialFilters = {
          year: yearNum,
          status,
          provider,
          advancedMode,
          fuzzy,
          fuzziness,
          expandSynonyms,
        };
        if (yearNum) {
          this.metadataYear.set(year);
        }
      }

      if (newInitialFilters) {
        this.initialFilters = newInitialFilters;
        this.onFiltersChanged(this.initialFilters);
      }

      // Only trigger search if params changed and query exists
      if (query && currentQueryString !== this.lastQueryString) {
        this.isPanelOpen.set(false);
        this.selectedResult.set(null);
        this.lastQueryString = currentQueryString;
        this.searchQuery = query;
        this.onSearch();
      }
    });
  }

  onSearchInput(value: string): void {
    this.suggestionsController.onSearchInput(value);
  }

  onSuggestionSelect(suggestion: Suggestion): void {
    this.suggestionsController.onSuggestionSelect(suggestion);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    const searchContainer = this.elementRef.nativeElement.querySelector('.search-container');
    if (searchContainer && !searchContainer.contains(target)) {
      this.showSuggestions.set(false);
    }
  }

  onSearchFocus(): void {
    this.suggestionsController.onSearchFocus();
  }

  onFiltersChanged(filters: FilterState): void {
    this.filterBadgeController.onFiltersChanged(filters);
  }

  onSearch(): void {
    const trimmedQuery = this.searchQuery.trim();
    if (!trimmedQuery) {
      this.queryMetadata.set(null);
      return;
    }

    this.isLoading.set(true);
    this.hasSearched.set(true);

    const advancedMode = this.currentFilters?.advancedMode || false;
    const fuzzy = this.currentFilters?.fuzzy || undefined;
    const fuzziness = this.currentFilters?.fuzziness || undefined;
    const expandSynonyms = this.currentFilters?.expandSynonyms || undefined;
    this.loadQueryMetadata(trimmedQuery);

    // Get year from filters or metadataYear signal
    const yearFilter = this.currentFilters?.year ?? this.metadataYear();
    const year = yearFilter
      ? typeof yearFilter === 'string'
        ? parseInt(yearFilter, 10)
        : yearFilter
      : undefined;

    // Get provider ID (undefined means "All" - no filter)
    const provider_id = this.currentFilters?.provider;

    // Map status to HTTP status code:
    // - 'active' = 200 (successful response)
    // - 'inactive' = 404 (not found - site is down/removed)
    // - 'any' = undefined (no filter)
    const statusFilter = this.currentFilters?.status;
    let status_code: number | undefined;
    if (statusFilter === 'active') {
      status_code = 200;
    } else if (statusFilter === 'inactive') {
      status_code = 404;
    }

    this.searchService
      .search(this.searchQuery, this.pageSize(), this.currentPage(), {
        advancedMode,
        fuzzy,
        fuzziness,
        expandSynonyms,
        year,
        provider_id,
        status_code,
      })
      .subscribe({
        next: response => {
          this.searchResults.set(response.results);
          this.totalCount.set(response.total);
          const suggestions = response.did_you_mean || [];
          if (suggestions.length > 0) {
            this.originalQuery.set(this.searchQuery);
          } else {
            this.originalQuery.set('');
          }
          this.didYouMeanSuggestions.set(suggestions);
          this.isLoading.set(false);

          // Save search to history if not a temporary search or pagination change
          if (!this.isTemporarySearch && !this.isPaginationChange && !this.isLoadedFromHistory) {
            const searchFilter: SearchFilter = {
              query: this.searchQuery,
            };

            if (this.currentFilters?.provider) {
              searchFilter.provider = this.currentFilters.provider;
            }
            if (this.currentFilters?.advancedMode) {
              searchFilter.advanced_mode = this.currentFilters.advancedMode;
            }
            if (this.currentFilters?.fuzzy) {
              searchFilter.fuzzy = this.currentFilters.fuzzy;
              if (this.currentFilters?.fuzziness) {
                searchFilter.fuzziness = this.currentFilters.fuzziness;
              }
              if (this.currentFilters?.expandSynonyms) {
                searchFilter.expand_synonyms = this.currentFilters.expandSynonyms;
              }
            }

            const searchItem = this.searchHistoryService.addSearch(searchFilter);
            this.currentSearchId = searchItem.id;

            // Build query params for URL
            const queryParams: Record<string, string> = { q: this.searchQuery, sid: searchItem.id };
            if (this.currentFilters?.provider)
              queryParams['provider'] = this.currentFilters.provider;
            if (this.currentFilters?.year) queryParams['year'] = String(this.currentFilters.year);
            if (this.currentFilters?.status && this.currentFilters.status !== 'any') {
              queryParams['status'] = this.currentFilters.status;
            }
            if (searchFilter.advanced_mode) {
              queryParams['advanced_mode'] = 'true';
            }
            if (searchFilter.fuzzy) {
              queryParams['fuzzy'] = 'true';
            }
            if (searchFilter.fuzziness) {
              queryParams['fuzziness'] = searchFilter.fuzziness;
            }
            if (searchFilter.expand_synonyms) {
              queryParams['expand_synonyms'] = 'true';
            }

            this.router.navigate(['/serps/search'], { queryParams, replaceUrl: true });
          }

          this.isLoadedFromHistory = false;
          this.isPaginationChange = false;
        },
        error: error => {
          console.error('Search error:', error);
          this.isLoading.set(false);
          this.searchResults.set([]);
          this.totalCount.set(0);
        },
      });
  }

  onMetadataIntervalChange(interval: 'day' | 'week' | 'month'): void {
    this.metadataInterval.set(interval);
    if (this.searchQuery.trim()) {
      this.loadQueryMetadata(this.searchQuery.trim());
    }
  }

  onResultClick(item: SearchResult | ProviderDetail | ArchiveDetail): void {
    const result = item as SearchResult;
    this.selectedResult.set(result);
    this.panelNavController.navigateToItem(result._id);

    if (!this.sessionService.sidebarCollapsed()) {
      this.sessionService.setSidebarCollapsed(true);
    }
  }

  onMetadataHistogramClick(payload: {
    year?: string;
    provider_id?: string;
    provider_name?: string;
  }): void {
    // Build query params starting from existing query
    const params: Record<string, string> = { q: this.searchQuery };

    // Preserve existing provider filter when available, otherwise fall back to payload provider
    const activeProvider = this.currentFilters?.provider;
    if (activeProvider) {
      params['provider'] = activeProvider;
    } else if (payload.provider_id) {
      params['provider'] = payload.provider_id;
    }

    // If year specified, use that (backend only supports year filter)
    if (payload.year) {
      params['year'] = payload.year;
    }

    // Preserve all active filters in URL params
    const status = this.currentFilters?.status ?? 'any';
    const advancedMode = this.currentFilters?.advancedMode ?? false;
    const fuzzy = this.currentFilters?.fuzzy ?? false;
    const fuzziness = this.currentFilters?.fuzziness ?? 'AUTO';
    const expandSynonyms = this.currentFilters?.expandSynonyms ?? false;

    // Add all filter params to URL so they are restored on navigation
    if (status && status !== 'any') {
      params['status'] = status;
    }
    if (advancedMode) {
      params['advanced_mode'] = 'true';
    }
    if (fuzzy) {
      params['fuzzy'] = 'true';
    }
    if (fuzziness && fuzziness !== 'AUTO') {
      params['fuzziness'] = fuzziness;
    }
    if (expandSynonyms) {
      params['expand_synonyms'] = 'true';
    }

    const yearNum = payload.year ? parseInt(payload.year, 10) : undefined;

    this.initialFilters = {
      year: yearNum,
      status,
      provider: activeProvider || payload.provider_id,
      advancedMode,
      fuzzy,
      fuzziness,
      expandSynonyms,
    };

    // Navigate to trigger a search with the new year while preserving other filters
    this.router.navigate(['/serps/search'], { queryParams: params });
  }

  onRelatedSerpSelected(result: SearchResult): void {
    this.selectedResult.set(result);
    this.panelNavController.navigateToItem(result._id);
  }

  onClosePanel(): void {
    this.panelNavController.closePanel();
    setTimeout(() => {
      this.selectedResult.set(null);
    }, 300);
  }

  handleSuggestionClick(suggestion: string): void {
    this.searchQuery = suggestion;
    this.currentPage.set(1);
    this.onSearch();
  }

  searchOriginalQuery(): void {
    const original = this.originalQuery();
    if (original) {
      this.searchQuery = original;
      this.originalQuery.set('');
      this.didYouMeanSuggestions.set([]);
      this.currentPage.set(1);
      this.onSearch();
    }
  }

  onPageChange(page: number): void {
    this.currentPage.set(page);
    this.isPaginationChange = true;
    this.onSearch();
    this.scrollToTop();
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.currentPage.set(1);
    this.isPaginationChange = true;
    this.updateSearchHistoryPageSize(size);
    this.onSearch();
  }

  loadSearchFromHistory(searchId: string): void {
    const searchItem = this.searchHistoryService.getSearch(searchId);
    if (searchItem) {
      this.currentSearchId = searchId;
      this.searchQuery = searchItem.filter.query;
      this.isLoading.set(true);
      this.hasSearched.set(true);
      this.loadQueryMetadata(searchItem.filter.query);

      // Update pagination state from stored search
      if (searchItem.filter.size) {
        this.pageSize.set(searchItem.filter.size);
      }
      if (searchItem.filter.page !== undefined) {
        this.currentPage.set(searchItem.filter.page);
      }

      // Restore filters if present
      if (searchItem.filter.provider) {
        this.initialFilters = {
          status: 'any',
          provider: searchItem.filter.provider,
        };
        this.onFiltersChanged(this.initialFilters);
      }

      this.searchService
        .search(searchItem.filter.query, searchItem.filter.size, searchItem.filter.page || 1)
        .subscribe({
          next: response => {
            this.searchResults.set(response.results);
            this.totalCount.set(response.total);
            this.isLoading.set(false);
          },
          error: error => {
            console.error('Search error:', error);
            this.isLoading.set(false);
            this.searchResults.set([]);
            this.totalCount.set(0);
          },
        });
    }
  }

  private loadQueryMetadata(query: string): void {
    this.isMetadataLoading.set(true);
    this.queryMetadata.set(null);

    this.searchService
      .getQueryMetadata({
        query,
        interval: this.metadataInterval(),
        top_n_queries: this.metadataTopQueries,
        top_providers: this.metadataTopProviders,
        top_archives: this.metadataTopArchives,
        last_n_months: this.metadataLastMonths,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: response => {
          this.queryMetadata.set(response);
          this.isMetadataLoading.set(false);
        },
        error: error => {
          console.error('Metadata error:', error);
          this.isMetadataLoading.set(false);
        },
      });
  }

  private scrollToTop(): void {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  private updateSearchHistoryPageSize(size: number): void {
    if (!this.currentSearchId || this.isTemporarySearch) {
      return;
    }

    const searchItem = this.searchHistoryService.getSearch(this.currentSearchId);
    if (searchItem) {
      this.searchHistoryService.updateSearch(this.currentSearchId, {
        ...searchItem.filter,
        size,
        page: 1,
      });
    }
  }
}
