import {
  ChangeDetectionStrategy,
  Component,
  signal,
  inject,
  computed,
  OnInit,
} from '@angular/core';

import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { TranslateModule } from '@ngx-translate/core';
import { AqlButtonComponent, AqlTooltipDirective } from 'aql-stylings';
import { LanguageSelectorComponent } from '../language-selector/language-selector.component';
import { SessionService } from '../../services/session.service';

// #region LEGACY - Uncomment when implementing user-based session storage
// import { FormsModule } from '@angular/forms';
// import {
//   AqlGroupItemComponent,
//   AqlDropdownComponent,
//   AqlInputFieldComponent,
//   AqlModalComponent,
//   AqlAvatarCardComponent,
// } from 'aql-stylings';
// import { UserData } from '../../models/user-data.model';
// import { ProjectService } from '../../services/project.service';
// #endregion LEGACY

interface NavItem {
  id: string;
  label: string;
  icon: string;
  route: string;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [
    TranslateModule,
    AqlButtonComponent,
    AqlTooltipDirective,
    LanguageSelectorComponent,
    AqlButtonComponent,
  ],
  templateUrl: './app-sidebar.component.html',
  styleUrl: './app-sidebar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppSidebarComponent implements OnInit {
  readonly sessionService = inject(SessionService);
  readonly router = inject(Router);
  readonly isCollapsed = this.sessionService.sidebarCollapsed;
  readonly activeRoute = signal<string>('/');
  readonly navItems: NavItem[] = [
    { id: 'serps', label: 'sidebar.serps', icon: 'bi-search', route: '/' },
    { id: 'providers', label: 'sidebar.providers', icon: 'bi-globe', route: '/providers' },
    { id: 'archives', label: 'sidebar.archives', icon: 'bi-archive', route: '/archives' },
    {
      id: 'compare',
      label: 'sidebar.compare',
      icon: 'bi-layout-split',
      route: '/compare',
    },
  ];
  readonly isActiveRoute = computed(() => {
    const current = this.activeRoute();
    return (route: string) => {
      if (route === '/') {
        return (
          current === '/' || (current.startsWith('/serps') && !current.startsWith('/serps/compare'))
        );
      }
      if (route === '/compare') {
        return current.startsWith('/compare') || current.startsWith('/serps/compare');
      }
      return current.startsWith(route);
    };
  });

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((event: NavigationEnd) => {
        this.activeRoute.set(event.urlAfterRedirects || event.url);
      });
  }

  ngOnInit(): void {
    this.activeRoute.set(this.router.url);
  }

  toggleCollapsed(force?: boolean): void {
    const newValue = typeof force === 'boolean' ? force : !this.isCollapsed();
    this.sessionService.setSidebarCollapsed(newValue);
  }

  navigateTo(route: string): void {
    this.router.navigate([route]);
  }

  // #region LEGACY - Uncomment when implementing user-based session storage
  /*
  readonly projectService = inject(ProjectService);
  readonly newProject = output<void>();
  readonly selectedItemId = signal<string | null>(null);
  readonly editingProjectId = signal<string | null>(null);
  readonly editingSearchId = signal<string | null>(null);
  readonly editingValue = signal<string>('');
  readonly deleteModal = viewChild<AqlModalComponent>('deleteModal');
  readonly itemToDelete = signal<{
    type: 'project' | 'search';
    id: string;
    name: string;
  } | null>(null);
  readonly allMenuItems = viewChildren(AqlMenuItemComponent);
  readonly projects = this.projectService.projects;
  readonly filteredProjects = computed(() => {
    const allProjects = this.projects();

    // Sort: pinned first (newest pins first), then unpinned by creation date (newest first)
    const sortedProjects = [...allProjects].sort((a, b) => {
      // Both pinned: sort by pinnedAt (newest first)
      if (a.isPinned && b.isPinned) {
        const aPinnedAt = a.pinnedAt ? new Date(a.pinnedAt).getTime() : 0;
        const bPinnedAt = b.pinnedAt ? new Date(b.pinnedAt).getTime() : 0;
        return bPinnedAt - aPinnedAt;
      }

      if (a.isPinned && !b.isPinned) return -1;
      if (!a.isPinned && b.isPinned) return 1;

      // Both unpinned: sort by creation date (newest first)
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });

    return sortedProjects.map(project => ({
      id: project.id,
      name: project.name,
      isPinned: project.isPinned || false,
      items: project.searches
        .slice()
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
        .map(search => ({
          id: search.id,
          name: search.label,
        })),
    }));
  });

  onItemSelected(itemId: string): void {
    const project = this.projectService.projects().find(p => p.searches.some(s => s.id === itemId));
    const search = project?.searches.find(s => s.id === itemId);

    if (search && project) {
      this.projectService.setActiveProject(project.id);

      const queryParams: Record<string, string> = {
        q: search.filter.query,
        sid: itemId,
      };
      if (search.filter.provider) queryParams['provider'] = search.filter.provider;
      if (search.filter.year) queryParams['year'] = String(search.filter.year);

      this.router.navigate(['/serps'], { queryParams });
    }
  }

  onNewProject(): void {
    this.projectService.createProject();
    this.newProject.emit();
    this.router.navigate(['/']);
  }

  onTemporarySearch(): void {
    this.router.navigate(['/'], { queryParams: { temp: 'true' } });
  }

  onAddToProject(projectId: string): void {
    this.projectService.setActiveProject(projectId);
    this.router.navigate(['/']);
  }

  onPinProject(projectId: string): void {
    this.projectService.pinProject(projectId);
  }

  onRenameProject(projectId: string): void {
    const project = this.projectService.getProject(projectId);
    if (project) {
      this.editingProjectId.set(projectId);
      this.editingValue.set(project.name);
      this.focusAndSelectInput(`aql-input-field[data-project-id="${projectId}"]`);
    }
  }

  onSaveProjectName(projectId: string): void {
    const newName = this.editingValue().trim();
    if (newName) {
      this.projectService.renameProject(projectId, newName);
    }
    this.editingProjectId.set(null);
    this.editingValue.set('');
  }

  onCancelProjectEdit(): void {
    this.editingProjectId.set(null);
    this.editingValue.set('');
  }

  onProjectNameKeydown(event: KeyboardEvent, projectId: string): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.onSaveProjectName(projectId);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      this.onCancelProjectEdit();
    }
  }

  onDeleteProject(projectId: string): void {
    const project = this.projectService.getProject(projectId);
    if (project) {
      this.itemToDelete.set({ type: 'project', id: project.id, name: project.name });
      this.deleteModal()?.open();
    }
  }

  onRenameSearch(searchId: string): void {
    const search = this.projectService
      .projects()
      .flatMap(p => p.searches)
      .find(s => s.id === searchId);
    if (search) {
      this.editingSearchId.set(searchId);
      this.editingValue.set(search.label);
      this.focusAndSelectInput(`aql-input-field[data-search-id="${searchId}"]`);
    }
  }

  onSaveSearchName(searchId: string): void {
    const newLabel = this.editingValue().trim();
    if (newLabel) {
      this.projectService.renameSearch(searchId, newLabel);
    }
    this.editingSearchId.set(null);
    this.editingValue.set('');
  }

  onCancelSearchEdit(): void {
    this.editingSearchId.set(null);
    this.editingValue.set('');
  }

  onSearchNameKeydown(event: KeyboardEvent, searchId: string): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.onSaveSearchName(searchId);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      this.onCancelSearchEdit();
    }
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    const editingProjectId = this.editingProjectId();
    const editingSearchId = this.editingSearchId();

    if (editingProjectId) {
      const inputField = document.querySelector(
        `aql-input-field[data-project-id="${editingProjectId}"]`,
      );
      if (inputField && !inputField.contains(target)) {
        this.onSaveProjectName(editingProjectId);
      }
    }

    if (editingSearchId) {
      const inputField = document.querySelector(
        `aql-input-field[data-search-id="${editingSearchId}"]`,
      );
      if (inputField && !inputField.contains(target)) {
        this.onSaveSearchName(editingSearchId);
      }
    }
  }

  onDeleteSearch(searchId: string): void {
    const search = this.projectService.projects().flatMap(p => {
      const s = p.searches.find(search => search.id === searchId);
      return s ? [s] : [];
    })[0];

    if (search) {
      this.itemToDelete.set({ type: 'search', id: search.id, name: search.label });
      this.deleteModal()?.open();
    }
  }

  confirmDelete(): void {
    const item = this.itemToDelete();
    if (!item) return;

    if (item.type === 'project') {
      const projectData = this.projectService.getProject(item.id);
      const isAnySearchActive = projectData?.searches.some(
        search => search.id === this.selectedItemId(),
      );

      this.projectService.deleteProject(item.id);
      if (isAnySearchActive) {
        this.router.navigate(['/']);
      }
    } else {
      let parentProjectId: string | undefined;
      this.projectService.projects().forEach(p => {
        if (p.searches.find(s => s.id === item.id)) {
          parentProjectId = p.id;
        }
      });

      const isActive = this.selectedItemId() === item.id;
      this.projectService.deleteSearch(item.id);

      if (isActive && parentProjectId) {
        this.projectService.setActiveProject(parentProjectId);
        this.router.navigate(['/']);
      }
    }

    this.deleteModal()?.close();
    this.itemToDelete.set(null);
  }

  cancelDelete(): void {
    this.deleteModal()?.close();
    this.itemToDelete.set(null);
  }

  private updateSelectedItemFromRoute(url: string): void {
    if (url.includes('/serps')) {
      const params = new URLSearchParams(url.split('?')[1] || '');
      const searchId = params.get('sid');

      if (searchId) {
        this.selectedItemId.set(searchId);
      } else {
        this.selectedItemId.set(null);
      }
    } else {
      this.selectedItemId.set(null);
    }
  }

  private focusAndSelectInput(selector: string): void {
    setTimeout(() => {
      const inputField = document.querySelector(selector);
      if (inputField) {
        const nativeInput = inputField.querySelector('input') as HTMLInputElement;
        if (nativeInput) {
          nativeInput.focus();
          nativeInput.select();
        }
      }
    }, 50);
  }
  */
  // #endregion LEGACY
}
