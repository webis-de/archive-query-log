import { Component, computed, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AppSidebarComponent } from './components/sidebar/app-sidebar.component';
import { SessionService } from './services/session.service';
import { ProjectService } from './services/project.service';
import { UserData } from './models/user-data.model';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, AppSidebarComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  private readonly sessionService = inject(SessionService);
  private readonly projectService = inject(ProjectService);

  title = 'aql-frontend';

  readonly userData = computed<UserData>(() => {
    const projects = this.projectService.projects();

    return {
      user: {
        name: 'User',
        institute: 'Archive Query Lab',
        avatarUrl: null,
      },
      projects: projects.map(project => ({
        id: project.id,
        name: project.name,
        items: project.searches.map(search => ({
          id: search.id,
          name: search.label,
          createdAt: new Date(search.createdAt),
        })),
        createdAt: new Date(project.createdAt),
      })),
    };
  });

  constructor() {
    this.sessionService.initializeSession();
  }
}
