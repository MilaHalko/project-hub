# F0 Scaffold and Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `frontend/` React app in its own nginx container (API proxied under `/api/`), with its tooling, its own CI workflow and the app shell (layout, loader bar, toasts, not-found page). The backend does not change.

**Architecture:** `frontend/Dockerfile` builds the app in a Node stage and serves `dist` from nginx; `frontend/nginx/` holds the server config with the cache rules, the SPA fallback, the security headers and the `/api/` proxy. `frontend/compose.yml` adds a `web` service to the unchanged root `docker-compose.yml`. The React app uses React Router at the root of its origin and TanStack Query; the shell lives in `frontend/src/ui/`.

**Tech Stack:** Node 26.13.1, npm, Vite 8, React 19, TypeScript 6.0 (typescript-eslint supports `<6.1`), ESLint 9 (eslint-plugin-jsx-a11y does not support ESLint 10 yet), Prettier, Vitest 5 + Testing Library + jsdom, Playwright test runner + `@axe-core/playwright`, `lucide-react`, `@fontsource/inter`, `@fontsource/space-mono`; nginx `nginxinc/nginx-unprivileged:1.30.6-alpine`.

**Spec:** [`docs/frontend/specs/2026-11-14-f0-scaffold-design.md`](../../frontend/specs/2026-11-14-f0-scaffold-design.md), parent [`docs/frontend/2026-11-14-frontend-design.md`](../../frontend/2026-11-14-frontend-design.md), look [`docs/frontend/style.md`](../../frontend/style.md).

## Revision (2026-11-14)

The first version of this plan served the app from FastAPI at `/app/` and was
built once in PR #14. The user then chose an own nginx container and a
backend left exactly as on `main`. The old Task 1 (`web.py`) is dropped, the
old Docker task moves into `frontend/`, and the base path changes from `/app/`
to `/`. The shell, loader bar and toasts are unchanged.

## Global Constraints

- CSP, verbatim: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
- Also on every nginx response: `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`.
- Cache: files under `/assets/` `public, max-age=31536000, immutable`; every other file and the fallback `no-cache`.
- `/api/<path>` → `http://api:8000/<path>`.
- No backend change: `git diff origin/main --stat -- src tests Dockerfile docker-compose.yml .github/workflows/ci.yml` stays empty; the root `.dockerignore` gains only `frontend/`; the root `README.md` gains at most one line.
- Nothing loads from another host: no Google Fonts, no CDN, no inline `<script>`.
- English only, sentence case, no "please", no "successfully", no exclamation marks.
- The course provider's company name appears nowhere (code, `package.json`, titles, headers).
- No comments or docstrings unless the code looks safe to remove but is not (`CLAUDE.md` "Comments"). Check every diff for new `#`, `//`, `/*`, `"""` lines before committing.
- Commits: one vertical slice each, plain-words imperative subject (≤70 chars), 1–3 line body. **Never add a `Co-Authored-By` trailer.**
- No tests that re-read config files (`package.json`, `Dockerfile`, nginx config, workflow, `.dockerignore`); tooling is proven by running it, the nginx rules by HTTP requests against the running container.
- Versions: `frontend/.nvmrc` = `26.13.1`; Docker `node:26.13.1-slim`; actions pinned by SHA: checkout `3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`, setup-node `949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0`, upload-artifact `cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2`.

## Review Focus

- A URL-encoded `..` (`/..%2f..%2fetc%2fpasswd`) must never read a file outside the web root → Task 2 test.
- `/index.html` requested by name must be `no-cache`, not immutable → Task 2 test.
- nginx drops inherited `add_header` lines in any `location` that adds its own: a 404 or an asset without the CSP → Task 2 test over files, fallback, 404 and the proxy.
- A future SPA route whose last segment has a dot (a login like `mila.k`) would get 404 by the extension rule: routes use ids, never logins, in the last segment. Recorded here for F1–F5.
- On a phone, Escape and a nav click close the menu, and Escape returns focus to the Menu button → Task 1 test.
- An error toast must not disappear on its own → Task 5 test.

---

### Task 1: Open the app shell in the dev server

**Files:** everything under `frontend/` except the Docker, nginx, compose and Playwright files; `.github/workflows/frontend.yml` (job `frontend`); root `README.md` (one line); root `.gitignore` (`.playwright-mcp/`).

**Interfaces:**
- `routes: RouteObject[]` (layout route, `index` → `ProjectsPage`, `*` → `NotFoundPage`); `AppProviders({children})`; `renderApp(path)` with `createMemoryRouter(routes, {initialEntries: [path]})`; `Banner({tag, title, children})`.
- npm scripts `dev`, `build` (`tsc -b && vite build`), `typecheck`, `lint` (`eslint . && prettier --check .`), `format`, `test` (`vitest run`), `e2e` (`playwright test`).
- Vite: `build.assetsInlineLimit: 0`; dev proxy `/api` → `http://localhost:8000`, prefix stripped; Vitest `jsdom`, `include: ['src/**/*.test.{ts,tsx}']`.

- [ ] Failing component tests: projects banner at `/`; skip link to `#main`; current page marked in nav "Main"; Menu opens and closes (Escape returns focus); menu closes after choosing a page; not found at `/no-such-page` with "Go to projects" → `href="/"`.
- [ ] Implement tokens, global styles, `Layout`, `Banner`, `ProjectsPage`, `NotFoundPage`, `main.tsx` with `createBrowserRouter(routes)`.
- [ ] `npm run lint && npm run typecheck && npm test && npm run build && npm audit --audit-level=high` → pass.
- [ ] Workflow `frontend.yml` (paths `frontend/**`, the workflow file), job `frontend`.
- [ ] Commit `Open the web app shell from the frontend dev server`.

### Task 2: Serve the app from its own nginx container with the API under /api/

**Files:** `frontend/Dockerfile`, `frontend/.dockerignore`, `frontend/nginx/default.conf`, `frontend/nginx/security-headers.conf`, `frontend/compose.yml`, `frontend/playwright.config.ts` (project `http`), `frontend/e2e/serving.spec.ts`, `frontend/package.json` + lockfile (`@playwright/test`, `@axe-core/playwright`), `.github/workflows/frontend.yml` (job `e2e`), root `.dockerignore` (`frontend/`), `frontend/README.md`.

- [ ] Failing tests in `serving.spec.ts` (Playwright `request`): fallback and deep link `no-cache` with `<div id="root">`; the first `/assets/*.js` from `index.html` immutable; `/index.html` and `/favicon.svg` `no-cache`; `/assets/missing.js`, `/missing.png`, `/projects/report.pdf` → 404 without the app; `/..%2f..%2fetc%2fpasswd` → no file content; `/api/health` → `{"status": "ok"}`; CSP, `no-referrer`, `nosniff` on all of them; `Server: nginx`.
- [ ] Run against the image with nginx's default config → header and fallback tests fail.
- [ ] Add the nginx config → `npx playwright test --project http` passes.
- [ ] Job `e2e`: start both compose files with a generated, masked `APP_JWT_SECRET`, `npx playwright test`, logs and report on failure, always `down -v`.
- [ ] Commit `Serve the web app from its own nginx container, API under /api/`.

### Task 3: Check the shell in a real browser with axe

**Files:** `frontend/e2e/fixtures.ts`, `frontend/e2e/shell.spec.ts`, `frontend/playwright.config.ts` (projects `desktop` 1280×800 and `phone` 375×812).

- [ ] Fixture: fail on console errors, page errors, requests to another origin; `expectAccessible(page)` with `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`.
- [ ] Tests: shell at `/` (phone: Menu opens, Escape closes and refocuses), not found → "Go to projects" → `/`, skip link focuses `main`.
- [ ] Commit `Check the web app shell in a real browser with axe`.

### Task 4: See a loader bar while requests run

Unchanged from the first version: `LoaderBar` (`role="progressbar"`, "Loading") while `useIsFetching() + useIsMutating() > 0`; `createQueryClient()`; tests for a query, a mutation, nothing running. Commit `See a loader bar at the top while requests run`.

### Task 5: Get toasts for finished actions

Unchanged from the first version: `useToast()` with `success`/`error`, regions `status` and `alert`, "Dismiss notification", success hides after 5000 ms, error stays. Commit `Show toasts for finished actions`.
