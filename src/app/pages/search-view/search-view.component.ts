import {
  Component,
  inject,
  OnInit,
  OnDestroy,
  signal,
  HostListener,
  ElementRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import {
  AqlHeaderBarComponent,
  AqlInputFieldComponent,
  AqlPanelComponent,
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlPaginationComponent,
  AqlMenuItemComponent,
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
import { Subscription } from 'rxjs';

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
    FilterDropdownComponent,
    AppQueryMetadataPanelComponent,
    QueryOverviewPanelComponent,
  ],
  templateUrl: './search-view.component.html',
  styleUrl: './search-view.component.css',
})
export class SearchViewComponent implements OnInit, OnDestroy {
  private readonly searchService = inject(SearchService);
  private readonly searchHistoryService = inject(SearchHistoryService);
  private readonly filterBadgeService = inject(FilterBadgeService);
  private readonly suggestionsService = inject(SuggestionsService);
  private readonly sessionService = inject(SessionService);
  private readonly languageService = inject(LanguageService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly translate = inject(TranslateService);
  private readonly elementRef = inject(ElementRef);

  searchQuery = '';
  searchResults: SearchResult[] = [];
  totalCount = 0;
  isLoading = false;
  hasSearched = false;
  currentSearchId?: string;
  isTemporarySearch = false;
  isPaginationChange = false;
  activeFilters: string[] = ['All'];
  initialFilters: FilterState | null = null;
  private currentFilters: FilterState | null = null;
  private langChangeSubscription?: Subscription;
  private metadataSubscription?: Subscription;

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

  ngOnInit(): void {
    // Subscribe to language changes to update badges
    this.langChangeSubscription = this.translate.onLangChange.subscribe(() => {
      if (this.currentFilters) {
        this.activeFilters = this.filterBadgeService.generateBadges(this.currentFilters);
      } else {
        this.activeFilters = [this.translate.instant('filter.badges.all') as string];
      }
    });

    this.route.queryParamMap.subscribe(queryParams => {
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
    });

    this.route.paramMap.subscribe(params => {
      this.isPanelOpen.set(false);
      this.selectedResult.set(null);

      const searchId = params.get('id');
      if (searchId === 'temp') {
        this.isTemporarySearch = true;
        this.currentSearchId = 'temp';

        // Check for query parameter
        this.route.queryParamMap.subscribe(queryParams => {
          const query = queryParams.get('q');
          if (query) {
            this.searchQuery = query;
            this.onSearch();
          }
        });
      } else if (searchId) {
        this.isTemporarySearch = false;
        this.loadSearchFromHistory(searchId);
      }
    });
  }

  onSearchInput(value: string): void {
    this.searchQuery = value;
    const trimmedValue = value.trim();
    if (trimmedValue.length >= this.suggestionsService.MINIMUM_QUERY_LENGTH) {
      this.suggestionsService.search(trimmedValue);
      this.showSuggestions.set(true);
    } else {
      this.suggestionsService.search('');
      this.showSuggestions.set(false);
    }
  }

  onSuggestionSelect(suggestion: Suggestion): void {
    this.searchQuery = suggestion.query;
    this.showSuggestions.set(false);
    this.onSearch();
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
    // Show suggestions again if there are any and query is long enough
    if (
      this.suggestions().length > 0 &&
      this.searchQuery.trim().length >= this.suggestionsService.MINIMUM_QUERY_LENGTH
    ) {
      this.showSuggestions.set(true);
    }
  }

  onFiltersChanged(filters: FilterState): void {
    this.currentFilters = filters;
    this.activeFilters = this.filterBadgeService.generateBadges(filters);
  }

  onSearch(): void {
    const trimmedQuery = this.searchQuery.trim();
    if (!trimmedQuery) {
      this.queryMetadata.set(null);
      return;
    }

    this.isLoading = true;
    this.hasSearched = true;

    const offset = (this.currentPage() - 1) * this.pageSize();
    this.loadQueryMetadata(trimmedQuery);

    this.searchService.search(this.searchQuery, this.pageSize(), offset).subscribe({
      next: response => {
        this.searchResults = response.results;
        this.totalCount = response.total;
        this.isLoading = false;

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
        this.isLoading = false;
        this.searchResults = [];
        this.totalCount = 0;
      },
    });
  }

  private loadSearchFromHistory(searchId: string): void {
    const searchItem = this.searchHistoryService.getSearch(searchId);
    if (searchItem) {
      this.currentSearchId = searchId;
      this.searchQuery = searchItem.filter.query;
      this.isLoading = true;
      this.hasSearched = true;
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
            this.searchResults = response.results;
            this.totalCount = response.total;
            this.isLoading = false;
          },
          error: error => {
            console.error('Search error:', error);
            this.isLoading = false;
            this.searchResults = [];
            this.totalCount = 0;
          },
        });
    }
  }

  private loadQueryMetadata(query: string): void {
    this.isMetadataLoading.set(true);
    this.queryMetadata.set(null);
    this.metadataSubscription?.unsubscribe();

    this.metadataSubscription = this.searchService
      .getQueryMetadata({
        query,
        interval: this.metadataInterval(),
        top_n_queries: this.metadataTopQueries,
        top_providers: this.metadataTopProviders,
        top_archives: this.metadataTopArchives,
        last_n_months: this.metadataLastMonths,
      })
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

  ngOnDestroy(): void {
    this.langChangeSubscription?.unsubscribe();
    this.metadataSubscription?.unsubscribe();
  }
}
