import { Component, inject, ChangeDetectionStrategy } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AppFooterComponent } from './components/footer/app-footer.component';
import { AppSidebarComponent } from './components/sidebar/app-sidebar.component';
import { SessionService } from './services/session.service';

// #region LEGACY - Uncomment when implementing user-based session storage
// import { computed } from '@angular/core';
// import { ProjectService } from './services/project.service';
// import { UserData } from './models/user-data.model';
// #endregion LEGACY

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, AppFooterComponent, AppSidebarComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  title = 'aql-frontend';

  private readonly sessionService = inject(SessionService);

  // #region LEGACY - Uncomment when implementing user-based session storage
  // private readonly projectService = inject(ProjectService);
  // readonly userData = computed<UserData>(() => {
  //   const projects = this.projectService.projects();
  //   return {
  //     user: {
  //       name: 'User',
  //       institute: 'Archive Query Lab',
  //       avatarUrl: null,
  //     },
  //     projects: projects.map(project => ({
  //       id: project.id,
  //       name: project.name,
  //       items: project.searches.map(search => ({
  //         id: search.id,
  //         name: search.label,
  //         createdAt: new Date(search.createdAt),
  //       })),
  //       createdAt: new Date(project.createdAt),
  //     })),
  //   };
  // });
  // #endregion LEGACY

  constructor() {
    this.sessionService.initializeSession();
  }
}
