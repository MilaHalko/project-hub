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
[`README.md`](../README.md). For the email join link to reach this dev server, start the API with
`APP_WEB_URL=http://localhost:5173`.

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
`X-Content-Type-Options: nosniff` (`nginx/security-headers.conf`). nginx accepts request bodies up to 11 MB
under `/api/`: one document may be 10 MB and the form around it needs room; with nginx's default of
1 MB a larger upload would stop at the proxy.

The access log writes each request's path and referrer without the query string, so the join
token of `/join?token=…` and `/api/join?token=…` never lands in it; `location = /api/join` also
keeps upstream errors for that path out of the error log, which would repeat the request line.
The `e2e` job checks the `web` log after the browser tests.

`compose.yml` adds a `web` service to the root `docker-compose.yml`, which stays as it is.
Run both from the repository root (paths in `compose.yml` are relative to the root):

```bash
APP_JWT_SECRET=$(openssl rand -hex 32) docker compose -f docker-compose.yml -f frontend/compose.yml up -d --build --wait
```

The app is then at <http://127.0.0.1:8080/> (`WEB_PORT` changes the host port), the API
under <http://127.0.0.1:8080/api/> and, as before, at <http://127.0.0.1:8000/docs>.
`compose.yml` also sets `APP_WEB_URL` on the API to `http://127.0.0.1:${WEB_PORT}` (override it
with `APP_WEB_URL`): the join link in a share mail opens the API's `GET /join`, which sends a
browser to this app's `/join` page. Open the app at that same address, because the sign-in lives
in the browser tab's storage of one origin.

## Browser tests

Playwright runs against the composed stack. Project `http` checks the nginx rules above with
plain HTTP requests.

```bash
npx playwright install chromium   # once
npm run e2e                       # E2E_BASE_URL overrides http://127.0.0.1:8080
```

Every page except log in needs a token, so tests start from `e2e/auth.ts`: `createUser(request)`
registers a unique login through `POST /api/auth` and returns its login and password;
`signIn(page, request)` (optionally with such a user) gets a token through `POST /api/login` and
puts it in `sessionStorage` before the app starts, once per tab, so a reload after a logout does
not bring the token back. A test that expects a 4xx answer adds
`test.use({ expectedApiStatuses: [401] })`, otherwise the console error Chromium logs for it fails
the test. To keep a local stack apart from other checkouts, run it under its own project name and
ports, for example
`APP_DB_PORT=55441 APP_PORT=8011 WEB_PORT=8091 APP_JWT_SECRET=$(openssl rand -hex 32) docker compose -p f1auth -f docker-compose.yml -f frontend/compose.yml up -d --build --wait`
from the repository root, then `E2E_BASE_URL=http://127.0.0.1:8091 npm run e2e`.

For the next epics: `signIn` seeds the token only once per tab and leaves the marker key
`project-hub.e2e-seeded` in `sessionStorage`; `createProjectViaApi(request, user, body)` in
`e2e/projects.ts` creates a project for that user through `POST /api/projects`, and
`inviteViaApi(request, owner, projectId, login)` adds a participant through the invite endpoint;
`createUser(request, { loginLength: 32 })` registers a login of that exact length. In unit tests
`mockApi` answers `GET /api/users/me`, the first projects page
(`GET /api/projects?limit=21&offset=0`, an empty list) and the members of any project (an empty
list) by default, so a test only lists the routes it cares about. `apiFetch` has the option
`endsSessionOn401`: a 401 clears the token and sends the user to log in, and only the logout call
turns it off. Page headings come from `Banner`, or from any plain `h1`; after navigation
`useFocusHeadingOnNavigate` gives that `h1` `tabindex="-1"` and focuses it, except after a redirect
on page load (such as `/` → `/projects`), where the focus stays where the browser put it.

Documents: `e2e/documents.ts` has `uploadViaApi(request, user, projectId, file)` and the small valid
files `samplePdf` and `sampleDocx` (from `e2e/files/`); `mockApi` answers
`GET /api/project/<id>/documents` with an empty list by default, so project page tests list only
the routes they care about.

Mail: `e2e/mail.ts` reads the mail the API sends from Mailpit's HTTP API at `E2E_MAIL_URL`
(default `http://127.0.0.1:8025`, the compose port `APP_MAIL_UI_PORT`); `readJoinLink(request, to)`
waits for the mail to that address and returns the join link in it. A stack on other ports needs
both variables, for example `E2E_BASE_URL=http://127.0.0.1:8091 E2E_MAIL_URL=http://127.0.0.1:8035`.

Dialogs use `ui/Dialog`, a native `<dialog>` opened with `showModal()`: the browser traps the
focus, closes it on Esc and returns the focus to the opener, so the end-to-end tests prove those.
jsdom has no `showModal`, so `src/test/setup.ts` stubs it (it sets `open`; `close()` removes it and
fires `close`), and component tests cover opening, closing and submitting. The projects list and
the project page keep their data for 30 seconds (`staleTime`); a change made in the app updates
`["project", id]` and refreshes every `["projects", …]` list itself.

## CI

`.github/workflows/frontend.yml` runs on pull requests and pushes to `main` that touch
`frontend/` or the workflow itself.

- Job `frontend`: `npm ci`, then the checks above.
- Job `e2e`: starts the composed stack and runs the browser tests.
