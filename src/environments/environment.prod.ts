// Production Environment Configuration
export const environment = {
  production: true,
  // In Kubernetes, the frontend nginx proxies /api/* to the backend service
  // This allows the frontend to work without knowing the backend's actual URL
  apiUrl: '/api',
  apiTimeout: 60000,
};
