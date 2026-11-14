FROM node:26.13.1-slim AS build

WORKDIR /web

COPY package.json package-lock.json ./
RUN npm ci

COPY . ./
RUN npm run build


FROM nginxinc/nginx-unprivileged:1.30.6-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /web/dist /usr/share/nginx/html

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
