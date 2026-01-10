# AqlFrontend

Angular 20.3.x standalone application with a custom `aql-stylings` library, styled using Tailwind CSS and daisyUI.

## Prerequisites

- Node.js **^20.19.0 || ^22.12.0 || ^24.0.0**

Check versions:

- `node -v`
- `npm -v`

## Quick Start

1. Install dependencies:
   - `npm install`
2. Configure API URL:
   - Development: `src/environments/environment.ts`
   - Production: `src/environments/environment.prod.ts`
3. Start dev server:
   - `npm run start`

App runs at `http://localhost:4200/`.

## Project Structure

- `src/` Angular app
- `projects/aql-stylings/` shared UI library
- `scripts/` repo utilities (formatting/validation helpers)

## Common Scripts

- `npm run start` start dev server
- `npm run watch` watch `aql-stylings` library in dev mode
- `npm run build` production build to `dist/aql-frontend/browser`
- `npm run lint` ESLint (Angular + TypeScript)
- `npm run format` Prettier format for `src/` and `projects/`
- `npm run reorder` auto-reorder class members to match lint ordering
- `npm run test` unit tests (Karma + Jasmine)
- `npm run test:ci` headless tests
- `npm run check-translations` validate i18n keys across languages

## Configuration

API base URL is read from:

- `src/environments/environment.ts` (dev)
- `src/environments/environment.prod.ts` (prod)

Endpoints are configured in `src/app/config/api.config.ts`.

## Linting and Formatting

- Lint: `npm run lint`
- Format: `npm run format`
- Reorder class members: `npm run reorder`

Member ordering is enforced by ESLint. If you reorder manually, run format afterward.

## Tests

- `npm run test` interactive
- `npm run test:ci` headless CI run

## Build

- `npm run build`

Output goes to `dist/aql-frontend/browser` (Angular application builder output).

## Docker

### Build the image

```bash
docker build -t aql-frontend:local .
```

### Run the container

```bash
docker run --rm -p 4200:80 --name aql-frontend aql-frontend:local
```

App is available at `http://localhost:4200/`.

### Notes

- The Docker image serves the app with NGINX using `nginx.conf`.
- Update `environment.prod.ts` before building the image to point at your production API.
