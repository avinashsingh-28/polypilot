# PolyPilot frontend: static build served by unprivileged nginx, which also reverse-proxies
# /api and /health to the backend so the browser uses a single origin (first-party cookies).
FROM node:22.11.0-alpine3.20 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# No secrets are ever passed to the frontend build.
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27.3-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.inc /etc/nginx/conf.d/security-headers.inc
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
