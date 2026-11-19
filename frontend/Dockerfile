FROM node:26.13.1-slim AS build

WORKDIR /web

COPY package.json package-lock.json ./
RUN npm ci

COPY . ./
RUN npm run build


FROM nginxinc/nginx-unprivileged:1.31.7-alpine

ENV API_UPSTREAM=api:8000
COPY nginx/default.conf /etc/nginx/templates/default.conf.template
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /web/dist /usr/share/nginx/html

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
