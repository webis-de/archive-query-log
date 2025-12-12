export interface SearchFilter {
  query: string;
  size?: number;
  offset?: number;
  timestamp?: string;
}

export interface SearchHistoryItem {
  id: string;
  projectId: string;
  filter: SearchFilter;
  createdAt: string;
  label: string;
}

export interface Project {
  id: string;
  name: string;
  createdAt: string;
  searches: SearchHistoryItem[];
  isPinned?: boolean;
  pinnedAt?: string;
}

export interface UserSession {
  userId: string;
  projects: Project[];
  activeProjectId?: string;
  sidebarCollapsed?: boolean;
  createdAt: string;
  lastActive: string;
}
