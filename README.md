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
2. Optional: build the `aql-stylings` library:
   - `npm run build:lib`

## Development server

- Start the library in watch mode (optional, for library-only development):
  - `npm run watch:lib`

- Start the app dev server (`http://localhost:4200/`):
  - `npm run start`
  - or `ng serve`

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

- Run unit tests (Karma + Jasmine, headless Chrome):
  - `npm run test`
  - or `ng test --watch=false --browsers=ChromeHeadless`

## TODO

- Implement daisyUI-based wrapper components inside the `aql-stylings` library (e.g. `aql-button`, `aql-input`, `aql-card`) that use daisyUI classes internally and expose a consistent, app-friendly API.

## Docker

To build and run the application using Docker, follow these steps:

### Build the Image

```bash
docker build -t aql-frontend:local .
```

### Run the Container

```bash
docker run --rm -p 4200:80 --name aql-frontend aql-frontend:local
```
The application will be accessible at `http://localhost:4200/`
