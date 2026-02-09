# Stage 1: Build web app with Angular.
FROM node:24-bookworm AS build
WORKDIR /app
# Copy only the package configuration files for dependencies.
COPY package*.json ./
# Install build dependencies.
RUN npm clean-install
# Copy remaining source code
COPY . .
# Build web app.
RUN npm run build -- --configuration=production

# Stage 2: Serve pre-built, static files with NGINX.
FROM nginx:stable-alpine AS runtime
# Add NGINX configuration for web app.
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Copy Angular build output to NGINX's web root.
COPY --from=build /app/dist/aql-frontend/browser /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# Default stage.
FROM runtime
