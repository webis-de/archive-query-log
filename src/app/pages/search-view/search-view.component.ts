import {
  Component,
  inject,
  signal,
  HostListener,
  ElementRef,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import {
  AqlHeaderBarComponent,
  AqlInputFieldComponent,
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlPaginationComponent,
  AqlMenuItemComponent,
} from 'aql-stylings';
import { SearchService } from '../../services/search.service';
import { SearchResult, QueryMetadataResponse } from '../../models/search.model';
import { SearchHistoryService } from '../../services/search-history.service';
import { LanguageSelectorComponent } from '../../components/language-selector/language-selector.component';
import { FilterBadgeService } from '../../services/filter-badge.service';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';
import { FilterDropdownComponent } from 'src/app/components/filter-dropdown/filter-dropdown.component';
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
    CommonModule,
    FormsModule,
    TranslateModule,
    RouterLink,
    AqlHeaderBarComponent,
    AqlInputFieldComponent,
    AqlDropdownComponent,
    AqlButtonComponent,
    LanguageSelectorComponent,
    AqlPaginationComponent,
    AqlMenuItemComponent,
    FilterDropdownComponent,
    AppQueryMetadataPanelComponent,
    QueryOverviewPanelComponent,
    SearchResultItemComponent,
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
  readonly translate = inject(TranslateService);
  readonly elementRef = inject(ElementRef);
  readonly destroyRef = inject(DestroyRef);
  readonly searchResults = signal<SearchResult[]>([]);
  readonly totalCount = signal<number>(0);
  readonly isLoading = signal<boolean>(false);
  readonly hasSearched = signal<boolean>(false);
  readonly metadataInterval = signal<'day' | 'week' | 'month'>('month');
  readonly metadataTopQueries = 10;
  readonly metadataTopProviders = 5;
  readonly metadataTopArchives = 5;
  readonly metadataLastMonths = 36;
  readonly isPanelOpen = signal(false);
  readonly selectedResult = signal<SearchResult | null>(null);
  readonly isSidebarCollapsed = this.sessionService.sidebarCollapsed;
  readonly currentPage = signal<number>(1);
  readonly pageSize = signal<number>(10);
  readonly queryMetadata = signal<QueryMetadataResponse | null>(null);
  readonly isMetadataLoading = signal<boolean>(false);
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
    this.filterBadgeController.refreshBadges();

    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe(queryParams => {
      const query = queryParams.get('q');
      const fromTimestamp = queryParams.get('from_timestamp') || '';
      const toTimestamp = queryParams.get('to_timestamp') || '';
      const status = queryParams.get('status') || 'any';
      const providerStr = queryParams.get('provider');
      const providers = providerStr ? providerStr.split(',') : [];
      const advancedMode = queryParams.get('advanced_mode') === 'true';
      const isTemp = queryParams.get('temp') === 'true';
      const searchId = queryParams.get('sid');

      // Set search ID if loading from history
      if (searchId) {
        this.currentSearchId = searchId;
        this.isLoadedFromHistory = true;
      }

      this.isTemporarySearch = isTemp;

      // Build current query string for comparison
      const currentQueryString = JSON.stringify({
        q: query,
        from_timestamp: fromTimestamp,
        to_timestamp: toTimestamp,
        status,
        provider: providerStr,
        advanced_mode: advancedMode,
      });

      // Update filters
      if (
        fromTimestamp ||
        toTimestamp ||
        status !== 'any' ||
        providers.length > 0 ||
        advancedMode
      ) {
        this.initialFilters = {
          dateFrom: fromTimestamp,
          dateTo: toTimestamp,
          status,
          providers,
          advancedMode,
        };
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

    const offset = (this.currentPage() - 1) * this.pageSize();
    const advancedMode = this.currentFilters?.advancedMode || false;
    this.loadQueryMetadata(trimmedQuery);

    this.searchService.search(this.searchQuery, this.pageSize(), offset, advancedMode).subscribe({
      next: response => {
        this.searchResults.set(response.results);
        this.totalCount.set(response.total);
        this.isLoading.set(false);

        // Save search to history if not a temporary search or pagination change
        if (!this.isTemporarySearch && !this.isPaginationChange && !this.isLoadedFromHistory) {
          const searchFilter: SearchFilter = {
            query: this.searchQuery,
          };

          if (this.currentFilters?.providers && this.currentFilters.providers.length > 0) {
            searchFilter.provider = this.currentFilters.providers.join(',');
          }
          if (this.currentFilters?.dateFrom) {
            searchFilter.from_timestamp = this.currentFilters.dateFrom;
          }
          if (this.currentFilters?.dateTo) {
            searchFilter.to_timestamp = this.currentFilters.dateTo;
          }
          if (this.currentFilters?.advancedMode) {
            searchFilter.advanced_mode = this.currentFilters.advancedMode;
          }

          const searchItem = this.searchHistoryService.addSearch(searchFilter);
          this.currentSearchId = searchItem.id;

          // Build query params for URL
          const queryParams: Record<string, string> = { q: this.searchQuery, sid: searchItem.id };
          if (searchFilter.provider) queryParams['provider'] = searchFilter.provider;
          if (searchFilter.from_timestamp)
            queryParams['from_timestamp'] = searchFilter.from_timestamp;
          if (searchFilter.to_timestamp) queryParams['to_timestamp'] = searchFilter.to_timestamp;
          if (this.currentFilters?.status && this.currentFilters.status !== 'any') {
            queryParams['status'] = this.currentFilters.status;
          }
          if (searchFilter.advanced_mode) {
            queryParams['advanced_mode'] = 'true';
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

  onResultClick(result: SearchResult): void {
    this.selectedResult.set(result);
    this.isPanelOpen.set(true);

    if (!this.sessionService.sidebarCollapsed()) {
      this.sessionService.setSidebarCollapsed(true);
    }
  }

  onRelatedSerpSelected(result: SearchResult): void {
    this.selectedResult.set(result);
  }

  onClosePanel(): void {
    this.isPanelOpen.set(false);
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
      if (searchItem.filter.offset !== undefined && searchItem.filter.size) {
        const page = Math.floor(searchItem.filter.offset / searchItem.filter.size) + 1;
        this.currentPage.set(page);
      }

      // Restore filters if present
      if (
        searchItem.filter.provider ||
        searchItem.filter.from_timestamp ||
        searchItem.filter.to_timestamp ||
        searchItem.filter.advanced_mode
      ) {
        this.initialFilters = {
          dateFrom: searchItem.filter.from_timestamp || '',
          dateTo: searchItem.filter.to_timestamp || '',
          status: 'any',
          providers: searchItem.filter.provider ? searchItem.filter.provider.split(',') : [],
          advancedMode: searchItem.filter.advanced_mode || false,
        };
        this.onFiltersChanged(this.initialFilters);
      }

      this.searchService
        .search(
          searchItem.filter.query,
          searchItem.filter.size,
          searchItem.filter.offset,
          searchItem.filter.advanced_mode,
        )
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
        offset: 0,
      });
    }
  }
}
