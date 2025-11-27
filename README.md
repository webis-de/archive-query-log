# AqlFrontend

Angular 20.3.x standalone application with a custom `aql-stylings` library, styled using Tailwind CSS and daisyUI.

## Prerequisites

- Node.js version **^20.19.0 || ^22.12.0 || ^24.0.0**

Check your versions:

- `node -v`
- `npm -v`

## Setup

1. Install dependencies:
   - `npm install`

2. Configure backend API URL (optional):
   - Development: `src/environments/environment.ts` (default: `http://localhost:8000`)
   - Production: `src/environments/environment.prod.ts`

## Development server

- Start the app dev server (`http://localhost:4200/`):
  - `npm run start`

- Watch the library in development mode:
  - `npm run watch`

The application automatically reloads when you change any source file.

## Build

- Build the app for production:
  - `npm run build`

Build artifacts are output to `dist/aql-frontend`.

## Linting

- Run ESLint:
  - `npm run lint`

## Formatting

- Run Prettier to format the source code:
  - `npm run format`

## Tests

- Run unit tests (Karma + Jasmine):
  - `npm run test`

- Run tests in CI mode:
  - `npm run test:ci`
