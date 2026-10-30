import { environment } from '../../environments/environment';

// Central configuration of the AQL API (endpoints are typed in `../api/schema.ts`)
export const API_CONFIG = {
  baseUrl: environment.apiUrl,
  timeout: 60000, // 60 seconds
} as const;
