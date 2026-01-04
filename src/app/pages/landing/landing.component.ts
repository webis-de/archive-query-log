import {
  AqlInputFieldComponent,
  AqlButtonComponent,
  AqlDropdownComponent,
  AqlMenuItemComponent,
} from 'aql-stylings';
import { Component, inject, signal, computed, HostListener, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs/operators';
import { SearchHistoryService } from '../../services/search-history.service';
import { ProjectService } from '../../services/project.service';
import { SessionService } from '../../services/session.service';
import { FilterBadgeService } from '../../services/filter-badge.service';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';
import { FilterDropdownComponent } from 'src/app/components/filter-dropdown/filter-dropdown.component';
import { FilterState } from '../../models/filter.model';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    AqlInputFieldComponent,
    AqlButtonComponent,
    AqlDropdownComponent,
    AqlMenuItemComponent,
    FilterDropdownComponent,
  ],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent {
  private readonly searchHistoryService = inject(SearchHistoryService);
  private readonly projectService = inject(ProjectService);
  private readonly sessionService = inject(SessionService);
  private readonly filterBadgeService = inject(FilterBadgeService);
  private readonly suggestionsService = inject(SuggestionsService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly elementRef = inject(ElementRef);

  private currentFilters: FilterState | null = null;

  readonly searchQuery = signal<string>('');
  readonly projects = this.projectService.projects;
  readonly session = this.sessionService.session;
  readonly activeFilters = signal<string[]>(['All']);
  readonly showSuggestions = signal<boolean>(false);
  readonly isTemporaryMode = toSignal(
    this.route.queryParams.pipe(map(params => params['temp'] === 'true')),
    { initialValue: false },
  );

  readonly suggestions = this.suggestionsService.suggestions;
  readonly activeProject = computed(() => {
    const currentSession = this.session();
    const activeProjectId = currentSession?.activeProjectId;
    const allProjects = this.projects();

    if (activeProjectId) {
      return allProjects.find(p => p.id === activeProjectId);
    }
    return null;
  });
  readonly hasProjects = computed(() => this.projects().length > 0);

  readonly landingMessage = computed(() => {
    if (this.isTemporaryMode()) {
      return 'Temporary search (not saved)';
    }
    const active = this.activeProject();
    if (active) {
      return `Search in "${active.name}"`;
    } else if (this.hasProjects()) {
      return 'Search the web archive';
    } else {
      return 'Create your first project and start searching';
    }
  });

  onSearchInput(value: string): void {
    this.searchQuery.set(value);
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
    this.searchQuery.set(suggestion.query);
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
      this.searchQuery().trim().length >= this.suggestionsService.MINIMUM_QUERY_LENGTH
    ) {
      this.showSuggestions.set(true);
    }
  }

  onFiltersChanged(filters: FilterState): void {
    this.currentFilters = filters;
    const badges = this.filterBadgeService.generateBadges(filters);
    this.activeFilters.set(badges);
  }

  onSearch(): void {
    const query = this.searchQuery().trim();
    if (query) {
      const queryParams: Record<string, string> = { q: query };

      if (this.currentFilters) {
        if (this.currentFilters.dateFrom) queryParams['dateFrom'] = this.currentFilters.dateFrom;
        if (this.currentFilters.dateTo) queryParams['dateTo'] = this.currentFilters.dateTo;
        if (this.currentFilters.status && this.currentFilters.status !== 'any')
          queryParams['status'] = this.currentFilters.status;
        if (this.currentFilters.providers && this.currentFilters.providers.length > 0) {
          queryParams['providers'] = this.currentFilters.providers.join(',');
        }
      }

      if (this.isTemporaryMode()) {
        // Route to temporary search view
        this.router.navigate(['/s', 'temp'], {
          queryParams: queryParams,
        });
      } else {
        // Normal search: save and navigate
        // Note: We might want to save filters in history too, but for now just passing them to the view
        const searchItem = this.searchHistoryService.addSearch({ query });
        this.router.navigate(['/s', searchItem.id], {
          queryParams: queryParams,
        });
      }
    }
  }
}
