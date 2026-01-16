import { Injectable, inject, computed } from '@angular/core';
import { SearchHistoryItem, SearchFilter } from '../models/project.model';
import { SessionService } from './session.service';
import { ProjectService } from './project.service';

@Injectable({
  providedIn: 'root',
})
export class SearchHistoryService {
  readonly searchHistory = computed(() => {
    const session = this.sessionService.session();
    if (!session) return [];
    return session.projects.flatMap(p => p.searches);
  });

  private readonly sessionService = inject(SessionService);
  private readonly projectService = inject(ProjectService);

  addSearch(filter: SearchFilter, projectId?: string): SearchHistoryItem {
    const session = this.sessionService.session() || this.sessionService.initializeSession();

    // Get or create active project
    let activeProjectId = projectId || session.activeProjectId;
    if (!activeProjectId) {
      const newProject = this.projectService.createProject();
      activeProjectId = newProject.id;
    }

    const project = this.projectService.getProject(activeProjectId);
    if (!project) {
      throw new Error('Project not found');
    }

    const searchItem: SearchHistoryItem = {
      id: this.sessionService.generateId(),
      projectId: activeProjectId,
      filter: {
        ...filter,
        timestamp: new Date().toISOString(),
      },
      createdAt: new Date().toISOString(),
      label: filter.query,
    };

    // Create new array reference to trigger reactivity
    const updatedSearches = [...project.searches, searchItem];
    this.projectService.updateProject(activeProjectId, { searches: updatedSearches });

    return searchItem;
  }

  getSearch(searchId: string): SearchHistoryItem | undefined {
    const session = this.sessionService.session();
    if (!session) return undefined;

    for (const project of session.projects) {
      const search = project.searches.find(s => s.id === searchId);
      if (search) return search;
    }

    return undefined;
  }

  getSearchesByProject(projectId: string): SearchHistoryItem[] {
    const project = this.projectService.getProject(projectId);
    return project?.searches || [];
  }

  updateSearch(searchId: string, filter: Partial<SearchFilter>): void {
    const session = this.sessionService.session();
    if (!session) return;

    for (const project of session.projects) {
      const search = project.searches.find(s => s.id === searchId);
      if (search) {
        search.filter = { ...search.filter, ...filter };
        this.projectService.updateProject(project.id, project);
        return;
      }
    }
  }

  deleteSearch(searchId: string): void {
    const session = this.sessionService.session();
    if (!session) return;

    for (const project of session.projects) {
      const searchIndex = project.searches.findIndex(s => s.id === searchId);
      if (searchIndex !== -1) {
        project.searches.splice(searchIndex, 1);
        this.projectService.updateProject(project.id, project);
        return;
      }
    }
  }
}
