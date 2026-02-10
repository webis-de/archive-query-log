import { environment } from '../../environments/environment';

// Central management of all backend endpoints
export const API_CONFIG = {
  baseUrl: environment.apiUrl,
  timeout: 60000, // 60 seconds

  endpoints: {
    // Search Engine Results Page
    serps: '/serps',
    serp: (serpId: string) => `/serps/${serpId}`,
    serpsPreview: '/serps/preview',
    // Providers
    providers: '/providers',
    provider: (providerId: string) => `/providers/${providerId}`,
    providerStatistics: (providerId: string) => `/providers/${providerId}/statistics`,
    // Archives
    archives: '/archives',
    archive: (archiveId: string) => `/archives/${archiveId}`,
    archiveStatistics: (archiveId: string) => `/archives/${archiveId}/statistics`,
  },
} as const;
