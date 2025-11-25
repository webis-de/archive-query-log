# --- Stage 1: Angular Build ---
FROM node:24-bookworm AS build

# Woprking directory in Container
WORKDIR /app

# Only copy package files to leverage npm cache
COPY package*.json ./

# Reproducible installation (devDependencies are needed for the build)
RUN npm install

# Copy remaining source code
COPY . .

# Production build (uses your existing npm script)
RUN npm run build -- --configuration=production

# --- Stage 2: NGINX Runtime ---
FROM nginx:stable-alpine AS runtime

# NGINX configuration for SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build output to /usr/share/nginx/html
# According to README: dist/aql-frontend
COPY --from=build /app/dist/aql-frontend/browser /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
