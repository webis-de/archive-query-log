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

## Docker

### For Users (Quick Start with Docker)

**Requirements:**
- Port 4200 available (or any port you choose)
- Docker (need to be logged in):
  ```bash
  docker login git.uni-jena.de
  ```

**Pull and run the latest image:**
```bash
docker pull git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/frontend:latest
```
```bash
docker run --rm -p 4200:80 git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/frontend:latest
```

The application will be accessible at `http://localhost:4200/`

> **Note:** The frontend expects the backend API to be available. For full functionality, also run the backend container.

### For Developers (Build Locally)

To build and run the application using Docker locally:

#### Build the Image

```bash
docker build -t aql-frontend:local .
```

#### Run the Container

```bash
docker run --rm -p 4200:80 --name aql-frontend aql-frontend:local
```

### Using Docker Compose

You can also use Docker Compose to build and run the frontend:

```bash
# Build and start the container
docker compose up --build

# Or run in detached mode
docker compose up -d --build

# Stop the container
docker compose down
```

The application will be accessible at `http://localhost:4200/`

## CI/CD Pipeline

The GitLab CI/CD pipeline automatically:

1. **install** - Installs npm dependencies
2. **lint** - Runs ESLint checks
3. **test** - Runs unit tests with Karma/Jasmine
4. **build** - Builds production bundle
5. **docker** - Builds and pushes Docker image to GitLab Container Registry

Docker images are automatically pushed to:
- `git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/frontend:latest` (main branch)
- `git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/frontend:<branch-slug>` (other branches)
