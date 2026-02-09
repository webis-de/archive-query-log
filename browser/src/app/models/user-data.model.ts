export interface SearchItem {
  id: string;
  name: string;
  createdAt?: Date;
  updatedAt?: Date;
}

export interface Project {
  id: string;
  name: string;
  items: SearchItem[];
  createdAt?: Date;
  updatedAt?: Date;
}

export interface User {
  name: string;
  institute: string;
  avatarUrl: string | null;
}

export interface UserData {
  user: User;
  projects: Project[];
}
