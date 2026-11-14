# F0 — Scaffold and shell

Date: 2026-11-14
Status: approved by the user (2026-11-14); serving changed by the user on
2026-11-14 from "FastAPI serves `/app/`" to "own nginx container"
Parent design: [`../2026-11-14-frontend-design.md`](../2026-11-14-frontend-design.md)
Roadmap row: [`../roadmap.md`](../roadmap.md) (F0)

## Intent

Lay the ground every later frontend epic stands on: a `frontend/` project with
its tooling, its own Docker image (nginx serving the build and proxying the API
under `/api/`), the agreed cache and security headers, the style tokens and
fonts, and an app shell (layout, loader bar, toasts, not-found page). No product
screens: sign-in comes in F1, projects in F2.

Everything the parent design decides (stack, serving rules, CSP text, CI jobs)
is taken as decided and not repeated here.

## Goals

- `frontend/` builds, lints, type-checks and tests with one command each, locally
  and in CI.
- `docker compose -f docker-compose.yml -f frontend/compose.yml up` starts the
  backend stack unchanged plus a `web` service at `http://127.0.0.1:8080/`.
- A first end-to-end test opens the app in a real browser against that stack,
  sees the shell and passes the axe check (WCAG 2.1 AA), at 1280 px and 375 px.

## Non-goals

- Any API call from the app's screens (no screen needs one yet).
- Sign-in, guarded routes, the token store (F1).
- `GET /join` handling (epic 10).
- Cloud hosting of the frontend (decided later; see the parent design).

## Anti-goals

Those of the parent design, in particular: no third-party hosts (fonts, scripts,
styles), no inline scripts, no company name of the course provider anywhere, and
**no backend change**: `src/`, `tests/`, the root `Dockerfile`, the root
`docker-compose.yml` and `.github/workflows/ci.yml` stay as they are on `main`;
the root `.dockerignore` gets only the line `frontend/`.

## Approaches

| Option | Trade-off | Decision |
|---|---|---|
| **nginx image: Node build stage, then nginx with its own config; `/api/` proxied to the `api` service** | The backend stays untouched; one origin for the browser (no CORS); headers and cache rules are a few lines of nginx config, tested over HTTP against the running container | **Chosen** (user, 2026-11-14) |
| FastAPI route `GET /app/{path}` that serves `frontend/dist` (built first) | One image; but frontend code in `main.py`, a Node stage in the backend Dockerfile and frontend tests in the backend suite | Rejected (user, 2026-11-14) |
| Node server (`vite preview` or a small Express app) in the web container | Same shape as nginx, but `vite preview` is not a production server and Express is own code to maintain | Rejected (builder's call) |

## Design

### Serving (`frontend/nginx/`)

- The image is `nginxinc/nginx-unprivileged` (stable, Alpine; runs as a
  non-root user, listens on 8080). Builder's call: the official `nginx` image
  starts as root.
- The app lives at the root of the web origin (Vite `base` `/`, no router
  basename).
- `/api/…` → `http://api:8000/…`, the `/api` prefix stripped, so the API keeps
  the spec paths.
- `/assets/…`: an existing file is served with `Cache-Control: public,
  max-age=31536000, immutable`; a missing one is `404`.
- Any other existing file (`index.html`, `favicon.svg`) is served with
  `Cache-Control: no-cache` (builder's call: only the hashed bundles under
  `/assets/` keep their name per content; a favicon cached for a year could
  never change).
- A missing path with a file extension is `404`, never `index.html`.
- Anything else → `index.html` with `Cache-Control: no-cache`.
- Every response (files, fallback, 404, proxied API responses) carries the CSP
  from the parent design, `Referrer-Policy: no-referrer` and
  `X-Content-Type-Options: nosniff`. The headers live in one file included in
  every `location`, because nginx drops inherited `add_header` lines in a
  block that adds its own.
- `server_tokens off`: the `Server` header names nginx without its version.
- Redirects are relative (`absolute_redirect off`), so they never name the
  container port; the API's own redirects come back under `/api/`.
- The `api` host name is re-resolved through Docker's DNS every 10 s, so
  recreating the API container does not leave nginx on a stale address.
- gzip for CSS, JavaScript and SVG.

### Docker and compose

- `frontend/Dockerfile`: stage `node:<.nvmrc version>-slim` runs `npm ci`,
  `npm run build`; the runtime stage copies the nginx config and `dist` only. A
  `HEALTHCHECK` asks nginx for `/`.
- `frontend/.dockerignore`: `node_modules/`, `dist/`, `playwright-report/`,
  `test-results/` (the host's `node_modules` holds macOS binaries of esbuild and
  rollup that break the Linux build).
- `frontend/compose.yml` adds `web` (built from `frontend/`, port
  `127.0.0.1:${WEB_PORT:-8080}:8080`, starts after `api` is healthy). The root
  `docker-compose.yml` is unchanged.
- Root `.dockerignore` gets `frontend/`.

### Frontend project

- Node: the current Active LTS (26.13.1 on 2026-11-14), pinned in
  `frontend/.nvmrc`; the Docker stage uses the same version.
- Libraries: React, React Router, TanStack Query (drives the loader bar),
  `lucide-react` for icons (builder's call: tree-shaken SVG components, no font
  or CDN). Dev: Vite, TypeScript, ESLint with `typescript-eslint`, `react-hooks`
  and `jsx-a11y` (builder's call: catches accessibility mistakes before the
  browser does), Prettier, Vitest, Testing Library, jsdom, Playwright test
  runner, `@axe-core/playwright`.
- `vite.config.ts`: `assetsInlineLimit: 0`, so fonts and icons are always files
  (a `data:` font would break `font-src 'self'`); the dev server proxies `/api/`
  to `localhost:8000` with the prefix stripped, as nginx does.
- npm scripts: `lint` (ESLint + Prettier check), `typecheck`, `test`, `build`,
  `e2e`, `format`.
- `frontend/README.md` explains how to run, check and test the app. The root
  `README.md` gets one line pointing to it.

### Style

- `src/styles/tokens.css`: the tokens from `style.md` as CSS variables.
- `src/styles/global.css`: base type (Inter 14 px), focus ring, reduced motion.
- Fonts: `@fontsource/inter` 400/500/600 and `@fontsource/space-mono` 400/700,
  Latin subset only, bundled by Vite into `/assets/`.

### App shell

The approved mockup: `.superpowers/f0/shell-mockup.png` (not committed; thrown
away after F0).

- **Layout**: "Skip to content" link, sidebar 220 px (logo mark with the
  holographic gradient, "Project Hub", nav with "Projects"), content on white.
  Profile and Log out appear in F1, when they work: a dead link would be a silent
  failure.
- **Phone (below 768 px)**: the sidebar becomes a top bar with the logo and a
  "Menu" button (`aria-expanded`); the menu closes on navigation and on Escape.
- **Home `/`**: holographic banner (tag `PROJECT_HUB`, title "Your projects",
  text "Projects you own and projects you were invited to."), and one line
  below: "Sign-in and the projects list come next." F2 replaces the line with
  the list.
- **Loader bar**: 3 px violet bar at the very top, shown while TanStack Query
  has any query or mutation running; `role="progressbar"`, label "Loading";
  animation off under `prefers-reduced-motion`.
- **Toasts**: `useToast()` gives `success(text)` and `error(text)`; bottom right,
  bottom centre on phones; success uses `role="status"`, error `role="alert"`;
  close button "Dismiss notification"; success hides after 5 s, error stays
  until dismissed. In F0 no screen calls it yet; component tests prove it.
- **Not found**: any unknown path shows the banner (tag `ERROR 404`, title
  "Page not found", text "This page does not exist. Check the address or go
  back to your projects.") and the primary button "Go to projects".

### Tests

- Serving (Playwright `request`, no browser, against the running `web`
  container, project `http`): every serving rule above, the headers on files,
  fallback, 404 and the proxied API, a path that tries to leave the web root,
  the proxy with the prefix stripped (`/api/health`), the relative `/api`
  redirect, gzip on the bundles.
- Component (Vitest + Testing Library): layout and nav, menu button on phone
  width, loader bar shown and hidden, toasts (show, auto-hide, dismiss, roles),
  not-found page and its link.
- End-to-end (Playwright, Chromium, against the composed stack): projects
  `desktop` 1280 × 800 and `phone` 375 × 812. Open `/` and see the shell; open
  an unknown path and see the not-found page; on the phone open and close the
  menu; the skip link moves focus to the content. Each page passes axe with the
  tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`. Any console error (a CSP
  violation is one) or a request to another origin fails the test.

### CI

`.github/workflows/frontend.yml`, on pull requests and pushes to `main` that
touch `frontend/**` or the workflow itself. Builder's calls: Chromium only;
`e2e` runs `docker compose -f docker-compose.yml -f frontend/compose.yml up -d
--build --wait` with `APP_JWT_SECRET` from `openssl rand -hex 32`, then
`npx playwright test`; on failure the stack logs are printed and the report is
uploaded with `actions/upload-artifact`; the stack is always taken down.
Actions are pinned by SHA. `ci.yml` is unchanged.

## Acceptance criteria

| # | Criterion | Proven by |
|---|---|---|
| 1 | `/` and a deep link `/projects/7` return `index.html` with `no-cache` | Playwright `http` |
| 2 | An existing bundle under `/assets/` is served with the immutable cache; `/index.html` and `/favicon.svg` are `no-cache` | Playwright `http` |
| 3 | A missing `/assets/x.js`, `/x.png` or `/projects/report.pdf` is 404, not `index.html` | Playwright `http` |
| 4 | A path that tries to leave the web root does not serve a file from outside it | Playwright `http` |
| 5 | Every response (file, fallback, 404, proxied API) carries the CSP, `no-referrer`, `nosniff`; `Server` shows no version | Playwright `http` |
| 6 | `/api/health` reaches the API's `GET /health` (prefix stripped) | Playwright `http` |
| 7 | The backend is unchanged: `git diff origin/main --stat -- src tests Dockerfile docker-compose.yml .github/workflows/ci.yml` is empty, the root `.dockerignore` gains only `frontend/` | the command |
| 8 | The composed stack builds and starts with `--wait` | `docker compose … up -d --build --wait` locally and in CI |
| 9 | Lint, type check, component tests, build, audit pass | `npm run lint`, `typecheck`, `test`, `build`, `npm audit --audit-level=high` |
| 10 | The shell shows the sidebar on desktop and a working menu button on a phone | Vitest + Playwright |
| 11 | The loader bar shows while a request runs and hides after | Vitest |
| 12 | Toasts show, hide after 5 s (success), close on Dismiss, use the right roles | Vitest |
| 13 | An unknown path shows "Page not found" with a link to projects | Vitest + Playwright |
| 14 | Every page visited passes axe (WCAG 2.1 AA) at 1280 and 375 px; no console errors | Playwright |
| 15 | No request leaves the origin (fonts self-hosted) | Playwright (fails on any request to another host) |
| 16 | CI jobs `frontend` and `e2e` are green | GitHub |

## Left to the builder

File and component names inside the agreed layout, the exact loader animation,
the icon for "Projects", the nginx config layout.

## Carried to later epics

- F1: query client defaults (`retry`, `refetchOnWindowFocus`; a 401 must not be
  retried); route-change focus management (focus `h1`/`main` on navigation,
  which also fixes focus loss after choosing a phone menu item); buttons and
  hover colour as tokens instead of hard-coded `#2b2b30`, 13 px and 7 px; the
  fetch wrapper prefixes every API path with `/api`.
- F2, before the first `useToast()` call: toast regions `aria-atomic="false"` +
  `aria-relevant="additions"`; pause the success auto-hide on hover and focus
  (WCAG 2.2.1); return focus after a keyboard dismiss; centre toasts on phones
  with `inset-inline: 16px` instead of `left: 50%` + `translateX`.
- Epic 10 (share links) or any feature that needs the client's address: the
  proxy sends `Host: api:8000` and no `X-Forwarded-For`/`-Proto`; add them
  together with the API's trusted-proxy setting.
- F4, before the first upload: nginx `client_max_body_size` (default 1 MB) must
  match the document size limit of epic 6.
