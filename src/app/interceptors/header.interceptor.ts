import { HttpInterceptorFn } from '@angular/common/http';

// Automatically adds standard headers to all outgoing requests
export const headerInterceptor: HttpInterceptorFn = (req, next) => {
  // Add default headers to all requests
  const modifiedReq = req.clone({
    setHeaders: {
      // 'Content-Type': 'application/json',
      // Accept: 'application/json',
      // 'X-API-Key': 'your-api-key',
      // 'X-Client-Version': '1.0.0',
    },
  });

  return next(modifiedReq);
};
