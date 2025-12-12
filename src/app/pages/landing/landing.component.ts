import { AqlInputFieldComponent, AqlButtonComponent } from 'aql-stylings';
import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';
import { SearchHistoryService } from '../../services/search-history.service';
import { ProjectService } from '../../services/project.service';
import { SessionService } from '../../services/session.service';
import { FilterBadgeService } from '../../services/filter-badge.service';
import { FilterDropdownComponent } from 'src/app/components/filter-dropdown/filter-dropdown.component';
import { LanguageSelectorComponent } from '../../components/language-selector/language-selector.component';
import { FilterState } from '../../models/filter.model';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TranslateModule,
    AqlInputFieldComponent,
    AqlButtonComponent,
    FilterDropdownComponent,
    LanguageSelectorComponent,
  ],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent implements OnInit {
  private readonly searchHistoryService = inject(SearchHistoryService);
  private readonly projectService = inject(ProjectService);
  private readonly sessionService = inject(SessionService);
  private readonly filterBadgeService = inject(FilterBadgeService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly searchQuery = signal<string>('');
  readonly projects = this.projectService.projects;
  readonly session = this.sessionService.session;
  readonly isTemporaryMode = signal<boolean>(false);
  readonly activeFilters = signal<string[]>(['All']);
  private currentFilters: FilterState | null = null;

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

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      this.isTemporaryMode.set(params['temp'] === 'true');
    });
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
