import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
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
import { AppMetadataPanelComponent } from '../../components/metadata-panel/metadata-panel.component';
import { SessionService } from '../../services/session.service';

@Component({
  selector: 'app-search-view',
  imports: [
    CommonModule,
    FormsModule,
    AqlHeaderBarComponent,
    AqlInputFieldComponent,
    AqlPanelComponent,
    AqlDropdownComponent,
    AqlButtonComponent,
    AppMetadataPanelComponent,
  ],
  templateUrl: './search-view.component.html',
  styleUrl: './search-view.component.css',
})
export class SearchViewComponent implements OnInit {
  private readonly searchService = inject(SearchService);
  private readonly searchHistoryService = inject(SearchHistoryService);
  private readonly sessionService = inject(SessionService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  searchQuery = '';
  searchResults: SearchResult[] = [];
  totalCount = 0;
  isLoading = false;
  hasSearched = false;
  currentSearchId?: string;
  isTemporarySearch = false;

  readonly isPanelOpen = signal(false);
  readonly selectedResult = signal<SearchResult | null>(null);
  readonly isSidebarCollapsed = this.sessionService.sidebarCollapsed;

  ngOnInit(): void {
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
    return new Date(dateString).toLocaleString('de-DE', {
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
}
