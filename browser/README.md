# AQL Browser Web App

This document describes the web app frontend for the AQL Browser, built with Angular. It serves as the user interface for visualizing and analyzing archived query logs.

The web app is implemented as an [Angular](https://angular.dev/) standalone application with custom styles using [Tailwind CSS](https://tailwindcss.com/) and [daisyUI](https://daisyui.com/).

## Prerequisites

To build or run the web app locally, first install Node.js.
We recommend one of the following versions: `^20.19.0`, `^22.12.0`, or `^24.0.0` (check using `node -v`).

## Quick Start

1. Navigate to the AQL browser directory: `cd browser/`
2. Install dependencies: `npm install`
3. Start a local development server: `npm run start`

Now, open the AQL Browser at `http://localhost:4200/`.

## Development

When working on the AQL Browser app, you can use the following scripts for development, testing, and building:

```shell
npm run start   # Start development server.
npm run watch   # Build `aql-stylings` library (reloads on changes)
npm run build   # Build production assets for deployment: `dist/aql-frontend/browser`
npm run lint    # Check code with ESLint (Angular and TypeScript).
npm run format  # Format code in `src/` and `projects/`.
npm run reorder # Auto-reorder class members to match lint ordering
npm run test    # Unit tests (Karma and Jasmine)
npm run test:ci # Headless unit tests (does not require a web browser)
npm run check-translations # Validate i18n keys of translation files.
```

## Configuration

The API URL can be specified in the environment configuration files, `src/environments/environment.ts` (production) and `src/environments/environment.development.ts` (development).
Further configuration options are available in the project files: `src/app/config/api.config.ts`.
