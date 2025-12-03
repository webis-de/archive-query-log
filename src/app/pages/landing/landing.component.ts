import { AqlInputFieldComponent, AqlButtonComponent } from 'aql-stylings';
import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { SearchHistoryService } from '../../services/search-history.service';
import { ProjectService } from '../../services/project.service';
import { SessionService } from '../../services/session.service';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule, FormsModule, AqlInputFieldComponent, AqlButtonComponent],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent implements OnInit {
  private readonly searchHistoryService = inject(SearchHistoryService);
  private readonly projectService = inject(ProjectService);
  private readonly sessionService = inject(SessionService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly searchQuery = signal<string>('');
  readonly projects = this.projectService.projects;
  readonly session = this.sessionService.session;
  readonly isTemporaryMode = signal<boolean>(false);

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

  onSearch(): void {
    const query = this.searchQuery().trim();
    if (query) {
      if (this.isTemporaryMode()) {
        // Route to temporary search view
        this.router.navigate(['/s', 'temp'], {
          queryParams: { q: query },
        });
      } else {
        // Normal search: save and navigate
        const searchItem = this.searchHistoryService.addSearch({ query });
        this.router.navigate(['/s', searchItem.id]);
      }
    }
  }
}
