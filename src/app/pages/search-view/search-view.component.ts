import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
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
} from 'aql-stylings';
import { SearchService } from '../../services/search.service';
import { SearchResult } from '../../models/search.model';
import { SearchHistoryService } from '../../services/search-history.service';
import { LanguageSelectorComponent } from '../../components/language-selector/language-selector.component';
import { LanguageService } from '../../services/language.service';
import { FilterBadgeService } from '../../services/filter-badge.service';
import { FilterDropdownComponent } from 'src/app/components/filter-dropdown/filter-dropdown.component';
import { FilterState } from '../../models/filter.model';
import { AppMetadataPanelComponent } from '../../components/metadata-panel/metadata-panel.component';
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
    FilterDropdownComponent,
    AppMetadataPanelComponent,
  ],
  templateUrl: './search-view.component.html',
  styleUrl: './search-view.component.css',
})
export class SearchViewComponent implements OnInit, OnDestroy {
  private readonly searchService = inject(SearchService);
  private readonly searchHistoryService = inject(SearchHistoryService);
  private readonly filterBadgeService = inject(FilterBadgeService);
  private readonly sessionService = inject(SessionService);
  private readonly languageService = inject(LanguageService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly translate = inject(TranslateService);

  searchQuery = '';
  searchResults: SearchResult[] = [];
  totalCount = 0;
  isLoading = false;
  hasSearched = false;
  currentSearchId?: string;
  isTemporarySearch = false;
  activeFilters: string[] = ['All'];
  initialFilters: FilterState | null = null;
  private currentFilters: FilterState | null = null;
  private langChangeSubscription?: Subscription;

  readonly isPanelOpen = signal(false);
  readonly selectedResult = signal<SearchResult | null>(null);
  readonly isSidebarCollapsed = this.sessionService.sidebarCollapsed;

  ngOnInit(): void {
    // Subscribe to language changes to update badges
    this.langChangeSubscription = this.translate.onLangChange.subscribe(() => {
      if (this.currentFilters) {
        this.activeFilters = this.filterBadgeService.generateBadges(this.currentFilters);
      } else {
        this.activeFilters = [this.translate.instant('filter.badges.all')];
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

  onFiltersChanged(filters: FilterState): void {
    this.currentFilters = filters;
    this.activeFilters = this.filterBadgeService.generateBadges(filters);
  }

  onSearch(): void {
    if (!this.searchQuery.trim()) {
      return;
    }

    this.isLoading = true;
    this.hasSearched = true;

    this.searchService.search(this.searchQuery).subscribe({
      next: response => {
        this.searchResults = response.results;
        this.totalCount = response.count;
        this.isLoading = false;

        // Only save search to history if it's not a temporary search
        if (!this.isTemporarySearch) {
          const searchItem = this.searchHistoryService.addSearch({
            query: this.searchQuery,
          });

          this.currentSearchId = searchItem.id;
          this.router.navigate(['/s', searchItem.id], { replaceUrl: true });
        }
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

      this.searchService
        .search(searchItem.filter.query, searchItem.filter.size, searchItem.filter.offset)
        .subscribe({
          next: response => {
            this.searchResults = response.results;
            this.totalCount = response.count;
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

  formatDate(dateString: string): string {
    const locale = this.languageService.getCurrentLanguageCode();
    return new Date(dateString).toLocaleString(locale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  onResultClick(result: SearchResult): void {
    this.selectedResult.set(result);
    this.isPanelOpen.set(true);

    if (!this.sessionService.sidebarCollapsed()) {
      this.sessionService.setSidebarCollapsed(true);
    }
  }

  onClosePanel(): void {
    this.isPanelOpen.set(false);
  }

  ngOnDestroy(): void {
    this.langChangeSubscription?.unsubscribe();
  }
}
