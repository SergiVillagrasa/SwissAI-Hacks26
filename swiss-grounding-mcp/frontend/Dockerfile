# Frontend (Vite/React SPA), served by nginx.
# Build context: swiss-grounding-mcp/frontend
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines VITE_* variables at build time, so they must be passed as
# Docker build args (Railway forwards service variables that match a
# declared ARG automatically for Dockerfile builds).
ARG VITE_AGENT_BACKEND_URL
ARG VITE_MAPBOX_TOKEN
ENV VITE_AGENT_BACKEND_URL=${VITE_AGENT_BACKEND_URL}
ENV VITE_MAPBOX_TOKEN=${VITE_MAPBOX_TOKEN}

RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# nginx's docker-entrypoint renders *.template files in
# /etc/nginx/templates into /etc/nginx/conf.d via envsubst, substituting
# only variables that exist in the environment (so $uri etc. in the
# template are left untouched). Railway injects PORT at runtime.
ENV PORT=8080
EXPOSE 8080
