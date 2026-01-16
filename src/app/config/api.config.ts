import { environment } from '../../environments/environment';

// Central management of all backend endpoints
export const API_CONFIG = {
  baseUrl: environment.apiUrl,
  timeout: 60000, // 60 seconds

  endpoints: {
    // Search Engine Results Page
    serps: '/api/serps',
    serp: (serpId: string) => `/api/serp/${serpId}`,
    serpsPreview: '/api/serps/preview',
    // Providers
    providers: '/api/providers',
    provider: (providerId: string) => `/api/providers/${providerId}`,
  },
} as const;
