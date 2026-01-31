import { Injectable, signal, computed } from '@angular/core';
import { UserSession } from '../models/project.model';

@Injectable({
  providedIn: 'root',
})
export class SessionService {
  readonly session = computed(() => this.sessionSignal());
  readonly sidebarCollapsed = computed(() => this.sessionSignal()?.sidebarCollapsed ?? true);

  private readonly STORAGE_KEY = 'aql_user_session';
  private readonly sessionSignal = signal<UserSession | null>(null);

  constructor() {
    const session = this.loadSession();
    this.sessionSignal.set(session);
  }

  initializeSession(): UserSession {
    let session = this.loadSession();

    if (!session) {
      session = {
        userId: this.generateId(),
        projects: [],
        createdAt: new Date().toISOString(),
        lastActive: new Date().toISOString(),
      };
      this.saveSession(session);
    } else {
      session.lastActive = new Date().toISOString();
      this.saveSession(session);
    }

    this.sessionSignal.set(session);
    return session;
  }

  updateSession(session: UserSession): void {
    const updatedSession = {
      ...session,
      lastActive: new Date().toISOString(),
    };
    this.saveSession(updatedSession);
    this.sessionSignal.set(updatedSession);
  }

  setActiveProject(projectId: string): void {
    const session = this.session();
    if (session) {
      const updatedSession = {
        ...session,
        activeProjectId: projectId,
      };
      this.updateSession(updatedSession);
    }
  }

  getActiveProjectId(): string | undefined {
    return this.session()?.activeProjectId;
  }

  setSidebarCollapsed(collapsed: boolean): void {
    const session = this.session();
    if (session) {
      const updatedSession = {
        ...session,
        sidebarCollapsed: collapsed,
      };
      this.updateSession(updatedSession);
    }
  }

  generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 15)}`;
  }

  private loadSession(): UserSession | null {
    const data = localStorage.getItem(this.STORAGE_KEY);
    if (data) {
      try {
        return JSON.parse(data);
      } catch (error) {
        console.error('Failed to parse session data:', error);
        localStorage.removeItem(this.STORAGE_KEY);
      }
    }
    return null;
  }

  private saveSession(session: UserSession): void {
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(session));
  }
}
