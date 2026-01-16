import {
  AqlInputFieldComponent,
  AqlButtonComponent,
  AqlDropdownComponent,
  AqlMenuItemComponent,
} from 'aql-stylings';
import {
  Component,
  inject,
  signal,
  computed,
  HostListener,
  ElementRef,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs/operators';
import { SearchHistoryService } from '../../services/search-history.service';
import { ProjectService } from '../../services/project.service';
import { SessionService } from '../../services/session.service';
import { FilterBadgeService } from '../../services/filter-badge.service';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';
import { FilterDropdownComponent } from 'src/app/components/filter-dropdown/filter-dropdown.component';
import { LanguageSelectorComponent } from '../../components/language-selector/language-selector.component';
import { FilterState } from '../../models/filter.model';
import { createFilterBadgeController } from '../../utils/filter-badges';
import { createSearchSuggestionsController } from '../../utils/search-suggestions';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TranslateModule,
    AqlInputFieldComponent,
    AqlButtonComponent,
    AqlDropdownComponent,
    AqlMenuItemComponent,
    FilterDropdownComponent,
    LanguageSelectorComponent,
  ],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LandingComponent {
  readonly searchHistoryService = inject(SearchHistoryService);
  readonly projectService = inject(ProjectService);
  readonly sessionService = inject(SessionService);
  readonly filterBadgeService = inject(FilterBadgeService);
  readonly suggestionsService = inject(SuggestionsService);
  readonly router = inject(Router);
  readonly route = inject(ActivatedRoute);
  readonly translate = inject(TranslateService);
  readonly elementRef = inject(ElementRef);
  readonly destroyRef = inject(DestroyRef);
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
      return this.translate.instant('landing.temporarySearchMode');
    }
    const active = this.activeProject();
    if (active) {
      return this.translate.instant('landing.searchingInProject', { name: active.name });
    } else if (this.hasProjects()) {
      return this.translate.instant('landing.searchLabel');
    } else {
      return this.translate.instant('landing.createProjectHint');
    }
  });

  private currentFilters: FilterState | null = null;
  private readonly filterBadgeController = createFilterBadgeController({
    filterBadgeService: this.filterBadgeService,
    translate: this.translate,
    destroyRef: this.destroyRef,
    getFilters: () => this.currentFilters,
    setFilters: filters => {
      this.currentFilters = filters;
    },
    setBadges: badges => this.activeFilters.set(badges),
  });
  private readonly suggestionsController = createSearchSuggestionsController({
    suggestionsService: this.suggestionsService,
    suggestions: this.suggestions,
    getQuery: () => this.searchQuery(),
    setQuery: value => this.searchQuery.set(value),
    showSuggestions: this.showSuggestions,
    onSearch: () => this.onSearch(),
  });

  constructor() {
    this.filterBadgeController.refreshBadges();
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
    const query = this.searchQuery().trim();
    if (query) {
      const queryParams: Record<string, string> = { q: query };

      if (this.currentFilters) {
        if (this.currentFilters.dateFrom)
          queryParams['from_timestamp'] = this.currentFilters.dateFrom;
        if (this.currentFilters.dateTo) queryParams['to_timestamp'] = this.currentFilters.dateTo;
        if (this.currentFilters.status && this.currentFilters.status !== 'any')
          queryParams['status'] = this.currentFilters.status;
        if (this.currentFilters.providers && this.currentFilters.providers.length > 0) {
          queryParams['provider'] = this.currentFilters.providers.join(',');
        }
      }

      // Save search to history with all parameters
      const searchFilter = {
        query,
        provider: queryParams['provider'],
        from_timestamp: queryParams['from_timestamp'],
        to_timestamp: queryParams['to_timestamp'],
      };

      if (!this.isTemporaryMode()) {
        this.searchHistoryService.addSearch(searchFilter);
      }

      // Navigate to search view with query params
      this.router.navigate(['/serps/search'], {
        queryParams: queryParams,
      });
    }
  }
}
