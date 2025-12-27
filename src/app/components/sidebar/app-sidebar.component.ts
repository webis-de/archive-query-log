import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  input,
  Output,
  signal,
  viewChildren,
  inject,
  computed,
  HostListener,
  OnInit,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs';
import { TranslateModule } from '@ngx-translate/core';
import {
  AqlGroupItemComponent,
  AqlMenuItemComponent,
  AqlButtonComponent,
  AqlAvatarCardComponent,
  AqlDropdownComponent,
  AqlInputFieldComponent,
} from 'aql-stylings';
import { UserData } from '../../models/user-data.model';
import { ProjectService } from '../../services/project.service';
import { SessionService } from '../../services/session.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TranslateModule,
    AqlGroupItemComponent,
    AqlMenuItemComponent,
    AqlButtonComponent,
    AqlAvatarCardComponent,
    AqlDropdownComponent,
    AqlInputFieldComponent,
  ],
  templateUrl: './app-sidebar.component.html',
  styleUrl: './app-sidebar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppSidebarComponent implements OnInit {
  private readonly projectService = inject(ProjectService);
  private readonly sessionService = inject(SessionService);
  private readonly router = inject(Router);

  readonly userData = input.required<UserData>();
  @Output() newProject = new EventEmitter<void>();

  readonly isCollapsed = this.sessionService.sidebarCollapsed;
  readonly selectedItemId = signal<string | null>(null);
  readonly editingProjectId = signal<string | null>(null);
  readonly editingSearchId = signal<string | null>(null);
  readonly editingValue = signal<string>('');

  readonly allMenuItems = viewChildren(AqlMenuItemComponent);

  readonly projects = this.projectService.projects;

  ngOnInit(): void {
    this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe((event: NavigationEnd) => {
        this.updateSelectedItemFromRoute(event.url);
      });

    this.updateSelectedItemFromRoute(this.router.url);
  }

  private updateSelectedItemFromRoute(url: string): void {
    // Extract search ID from URL
    const match = url.match(/\/s\/([^/]+)/);
    if (match && match[1] !== 'temp') {
      const searchId = match[1];
      this.selectedItemId.set(searchId);
    } else {
      // Clear selection if on landing page or temp search
      this.selectedItemId.set(null);
    }
  }

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
    this.router.navigate(['/s', itemId]);
  }

  toggleCollapsed(force?: boolean): void {
    const newValue = typeof force === 'boolean' ? force : !this.isCollapsed();
    this.sessionService.setSidebarCollapsed(newValue);
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
    if (project && confirm(`Delete project "${project.name}"?`)) {
      // Check if any search in this project is currently active
      const isAnySearchActive = project.searches.some(
        search => search.id === this.selectedItemId(),
      );

      this.projectService.deleteProject(projectId);
      if (isAnySearchActive) {
        this.router.navigate(['/']);
      }
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

  private focusAndSelectInput(selector: string): void {
    setTimeout(() => {
      const inputField = document.querySelector(selector);
      if (inputField) {
        // Find the native input element inside aql-input-field
        const nativeInput = inputField.querySelector('input') as HTMLInputElement;
        if (nativeInput) {
          nativeInput.focus();
          nativeInput.select();
        } else {
          console.warn('Native input not found for selector:', selector);
        }
      } else {
        console.warn('Input field not found for selector:', selector);
      }
    }, 50); // render timeout
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
    let parentProjectId: string | undefined;
    const search = this.projectService.projects().flatMap(p => {
      const s = p.searches.find(search => search.id === searchId);
      if (s) parentProjectId = p.id;
      return s ? [s] : [];
    })[0];

    if (search && confirm(`Delete search "${search.label}"?`)) {
      const isActive = this.selectedItemId() === searchId;
      this.projectService.deleteSearch(searchId);

      if (isActive && parentProjectId) {
        this.projectService.setActiveProject(parentProjectId);
        this.router.navigate(['/']);
      }
    }
  }
}
