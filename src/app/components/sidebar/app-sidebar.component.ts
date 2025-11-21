import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  input,
  Output,
  signal,
  viewChildren,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  AqlGroupItemComponent,
  AqlMenuItemComponent,
  AqlButtonComponent,
  AqlAvatarCardComponent,
  AqlDropdownComponent,
} from 'aql-stylings';
import { UserData } from '../../models/user-data.model';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [
    CommonModule,
    AqlGroupItemComponent,
    AqlMenuItemComponent,
    AqlButtonComponent,
    AqlAvatarCardComponent,
    AqlDropdownComponent,
  ],
  templateUrl: './app-sidebar.component.html',
  styleUrl: './app-sidebar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppSidebarComponent {
  readonly userData = input.required<UserData>();
  @Output() newProject = new EventEmitter<void>();

  readonly isCollapsed = signal(false);
  readonly selectedItemId = signal<string | null>(null);

  readonly allMenuItems = viewChildren(AqlMenuItemComponent);

  onItemSelected(itemId: string): void {
    this.selectedItemId.set(itemId);
  }

  get filteredProjects() {
    return this.userData().projects;
  }

  toggleCollapsed(force?: boolean): void {
    if (typeof force === 'boolean') {
      this.isCollapsed.set(force);
      return;
    }
    this.isCollapsed.update(value => !value);
  }

  onNewProject(): void {
    this.newProject.emit();
  }
}
