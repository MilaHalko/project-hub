# Project Hub web app

The React app for Project Hub. It is an addition beyond the spec and sits beside
the API: the backend does not depend on it. Its plan and decisions are in
[`docs/frontend/`](../docs/frontend/README.md).

## Requirements

Node 26.13.1 (pinned in `.nvmrc`) and npm. All commands run in `frontend/`.

## Run

```bash
npm ci
npm run dev        # http://localhost:5173/, /api/… proxied to the API on localhost:8000
```

The app calls the API under `/api/` (for example `/api/login` for `POST /login`); the dev
server strips the prefix, so start the API as described in the root
[`README.md`](../README.md).

## Checks

```bash
npm run lint       # ESLint and Prettier
npm run typecheck
npm test           # component tests (Vitest)
npm run build      # writes dist/
npm audit --audit-level=high
```

`npm run format` fixes formatting.

## Container

`Dockerfile` builds the app with Node and serves `dist/` from nginx (non-root, port 8080).
nginx proxies `/api/…` to the API with the prefix stripped, so the browser talks to one origin
and the API needs no CORS. Files under `/assets/` are cached for a year, everything else
(`index.html`, the favicon, deep links) is `no-cache`; a missing file is 404, any other path
gets `index.html`. Every response carries the CSP, `Referrer-Policy: no-referrer` and
`X-Content-Type-Options: nosniff` (`nginx/security-headers.conf`).

`compose.yml` adds a `web` service to the root `docker-compose.yml`, which stays as it is.
Run both from the repository root (paths in `compose.yml` are relative to the root):

```bash
APP_JWT_SECRET=$(openssl rand -hex 32) docker compose -f docker-compose.yml -f frontend/compose.yml up -d --build --wait
```

The app is then at <http://127.0.0.1:8080/> (`WEB_PORT` changes the host port), the API
under <http://127.0.0.1:8080/api/> and, as before, at <http://127.0.0.1:8000/docs>.

## Browser tests

Playwright runs against the composed stack. Project `http` checks the nginx rules above with
plain HTTP requests.

```bash
npx playwright install chromium   # once
npm run e2e                       # E2E_BASE_URL overrides http://127.0.0.1:8080
```

## CI

`.github/workflows/frontend.yml` runs on pull requests and pushes to `main` that touch
`frontend/` or the workflow itself.

- Job `frontend`: `npm ci`, then the checks above.
- Job `e2e`: starts the composed stack and runs the browser tests.
