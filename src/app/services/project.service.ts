import { Injectable, inject, computed } from '@angular/core';
import { Project } from '../models/project.model';
import { SessionService } from './session.service';

@Injectable({
  providedIn: 'root',
})
export class ProjectService {
  readonly projects = computed(() => {
    return this.sessionService.session()?.projects ?? [];
  });

  private readonly sessionService = inject(SessionService);

  constructor() {
    this.sessionService.initializeSession();
  }

  createProject(name?: string): Project {
    const session = this.sessionService.currentSession || this.sessionService.initializeSession();

    const project: Project = {
      id: this.sessionService.generateId(),
      name: name || `Project ${session.projects.length + 1}`,
      createdAt: new Date().toISOString(),
      searches: [],
    };

    // Create new array reference to trigger reactivity
    const updatedSession = {
      ...session,
      projects: [...session.projects, project],
      activeProjectId: project.id,
    };
    this.sessionService.updateSession(updatedSession);

    return project;
  }

  getProject(projectId: string): Project | undefined {
    return this.projects().find(p => p.id === projectId);
  }

  getActiveProject(): Project | undefined {
    const activeProjectId = this.sessionService.getActiveProjectId();
    if (activeProjectId) {
      return this.getProject(activeProjectId);
    }
    return undefined;
  }

  updateProject(projectId: string, updates: Partial<Project>): void {
    const session = this.sessionService.currentSession;
    if (!session) return;

    const projectIndex = session.projects.findIndex(p => p.id === projectId);
    if (projectIndex !== -1) {
      // Create new array with updated project to trigger reactivity
      const updatedProjects = [...session.projects];
      updatedProjects[projectIndex] = {
        ...updatedProjects[projectIndex],
        ...updates,
      };

      const updatedSession = {
        ...session,
        projects: updatedProjects,
      };
      this.sessionService.updateSession(updatedSession);
    }
  }

  deleteProject(projectId: string): void {
    const session = this.sessionService.currentSession;
    if (!session) return;

    const updatedProjects = session.projects.filter(p => p.id !== projectId);

    const updatedSession = {
      ...session,
      projects: updatedProjects,
      activeProjectId:
        session.activeProjectId === projectId ? updatedProjects[0]?.id : session.activeProjectId,
    };

    this.sessionService.updateSession(updatedSession);
  }

  setActiveProject(projectId: string): void {
    this.sessionService.setActiveProject(projectId);
  }

  pinProject(projectId: string): void {
    const project = this.getProject(projectId);
    if (project) {
      const isPinned = !project.isPinned;
      this.updateProject(projectId, {
        isPinned,
        pinnedAt: isPinned ? new Date().toISOString() : undefined,
      });
    }
  }

  renameProject(projectId: string, newName: string): void {
    if (!newName.trim()) return;

    const project = this.getProject(projectId);
    if (project) {
      this.updateProject(projectId, {
        name: newName.trim(),
      });
    }
  }

  renameSearch(searchId: string, newLabel: string): void {
    if (!newLabel.trim()) return;

    const session = this.sessionService.currentSession;
    if (!session) return;

    for (const project of session.projects) {
      const searchIndex = project.searches.findIndex(s => s.id === searchId);
      if (searchIndex !== -1) {
        const updatedSearches = [...project.searches];
        updatedSearches[searchIndex] = {
          ...updatedSearches[searchIndex],
          label: newLabel.trim(),
        };
        this.updateProject(project.id, { searches: updatedSearches });
        return;
      }
    }
  }

  deleteSearch(searchId: string): void {
    const session = this.sessionService.currentSession;
    if (!session) return;

    for (const project of session.projects) {
      const searchIndex = project.searches.findIndex(s => s.id === searchId);
      if (searchIndex !== -1) {
        const updatedSearches = project.searches.filter((_, i) => i !== searchIndex);
        this.updateProject(project.id, { searches: updatedSearches });
        return;
      }
    }
  }

  // Get all projects sorted by pinned status
  getSortedProjects(): Project[] {
    return [...this.projects()].sort((a, b) => {
      // Pinned projects first
      if (a.isPinned && !b.isPinned) return -1;
      if (!a.isPinned && b.isPinned) return 1;
      // Then by creation date (newest first)
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });
  }
}
