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
import { ActivatedRoute, Router } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { combineLatest } from 'rxjs';
import {
  AqlHeaderBarComponent,
  AqlInputFieldComponent,
  AqlPanelComponent,
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlPaginationComponent,
  AqlMenuItemComponent,
  AqlTooltipDirective,
} from 'aql-stylings';
import { SearchService } from '../../services/search.service';
import { SearchResult, QueryMetadataResponse } from '../../models/search.model';
import { SearchHistoryService } from '../../services/search-history.service';
import { LanguageSelectorComponent } from '../../components/language-selector/language-selector.component';
import { LanguageService } from '../../services/language.service';
import { FilterBadgeService } from '../../services/filter-badge.service';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';
import { FilterDropdownComponent } from 'src/app/components/filter-dropdown/filter-dropdown.component';
import { FilterState } from '../../models/filter.model';
import { AppQueryMetadataPanelComponent } from '../../components/query-metadata-panel/query-metadata-panel.component';
import { QueryOverviewPanelComponent } from '../../components/query-overview-panel/query-overview-panel.component';
import { SessionService } from '../../services/session.service';
import { createSearchSuggestionsController } from '../../utils/search-suggestions';
import { createFilterBadgeController } from '../../utils/filter-badges';

@Component({
  selector: 'app-search-view',
  imports: [
    CommonModule,
    FormsModule,
    TranslateModule,
    AqlHeaderBarComponent,
    AqlInputFieldComponent,
    AqlPanelComponent,
    AqlDropdownComponent,
    AqlButtonComponent,
    LanguageSelectorComponent,
    AqlPaginationComponent,
    AqlMenuItemComponent,
    AqlTooltipDirective,
    FilterDropdownComponent,
    AppQueryMetadataPanelComponent,
    QueryOverviewPanelComponent,
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
  readonly languageService = inject(LanguageService);
  readonly route = inject(ActivatedRoute);
  readonly router = inject(Router);
  readonly translate = inject(TranslateService);
  readonly elementRef = inject(ElementRef);
  readonly destroyRef = inject(DestroyRef);
  searchQuery = '';
  readonly searchResults = signal<SearchResult[]>([]);
  readonly totalCount = signal<number>(0);
  readonly isLoading = signal<boolean>(false);
  readonly hasSearched = signal<boolean>(false);
  currentSearchId?: string;
  isTemporarySearch = false;
  isPaginationChange = false;
  activeFilters: string[] = ['All'];
  initialFilters: FilterState | null = null;
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
  readonly suggestions = this.suggestionsService.suggestions;
  readonly showSuggestions = signal<boolean>(false);

  private currentFilters: FilterState | null = null;
  private lastRouteSearchId: string | null = null;
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

    combineLatest([this.route.paramMap, this.route.queryParamMap])
      .pipe(takeUntilDestroyed())
      .subscribe(([params, queryParams]) => {
        const dateFrom = queryParams.get('dateFrom') || '';
        const dateTo = queryParams.get('dateTo') || '';
        const status = queryParams.get('status') || 'any';
        const providersStr = queryParams.get('providers');
        const providers = providersStr ? providersStr.split(',') : [];

        if (dateFrom || dateTo || status !== 'any' || providers.length > 0) {
          this.initialFilters = {
            dateFrom,
            dateTo,
            status,
            providers,
          };
          // Update badges immediately
          this.onFiltersChanged(this.initialFilters);
        }

        const searchId = params.get('id');
        const isTemporary = searchId === 'temp';

        if (searchId !== this.lastRouteSearchId) {
          this.isPanelOpen.set(false);
          this.selectedResult.set(null);
          this.lastRouteSearchId = searchId;

          if (!isTemporary && searchId) {
            this.isTemporarySearch = false;
            this.loadSearchFromHistory(searchId);
          }
        }

        if (isTemporary) {
          this.isTemporarySearch = true;
          this.currentSearchId = 'temp';

          const query = queryParams.get('q');
          if (query) {
            this.searchQuery = query;
            this.onSearch();
          }
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
    this.loadQueryMetadata(trimmedQuery);

    this.searchService.search(this.searchQuery, this.pageSize(), offset).subscribe({
      next: response => {
        this.searchResults.set(response.results);
        this.totalCount.set(response.total);
        this.isLoading.set(false);

        // Only save search to history if it's not a temporary search or pagination change
        if (!this.isTemporarySearch && !this.isPaginationChange) {
          const searchItem = this.searchHistoryService.addSearch({
            query: this.searchQuery,
          });

          this.currentSearchId = searchItem.id;
          this.router.navigate(['/s', searchItem.id], { replaceUrl: true });
        }

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

  formatDate(dateString: string): string {
    return this.languageService.formatDate(dateString);
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

  private loadSearchFromHistory(searchId: string): void {
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

      this.searchService
        .search(searchItem.filter.query, searchItem.filter.size, searchItem.filter.offset)
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

  private updateSearchHistoryPageSize(size: number): void {
    if (!this.currentSearchId || this.currentSearchId === 'temp') {
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

  private scrollToTop(): void {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}
