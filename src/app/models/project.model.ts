export interface SearchFilter {
  query: string;
  size?: number;
  offset?: number;
  timestamp?: string;
  provider?: string;
  archive?: string;
  from_timestamp?: string;
  to_timestamp?: string;
  advanced_mode?: boolean;
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
