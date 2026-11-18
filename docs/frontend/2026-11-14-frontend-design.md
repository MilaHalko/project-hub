# Web frontend

Date: 2026-11-14
Status: approved by the user (2026-11-14); serving changed by the user on
2026-11-14 from "built into the API image" to "own nginx container"
Roadmap: [`roadmap.md`](roadmap.md) (frontend epics F0–F6, with F1b)
Style: [`style.md`](style.md), mockup [`mockups/look.html`](mockups/look.html)
Backend: [`docs/PRDs/roadmap.md`](../PRDs/roadmap.md), section "Frontend requests"

## Intent

The spec ([`docs/initial-spec.md`](../initial-spec.md)) asks for an API only. The
project is defended in front of a mentor, and a real web interface makes the
product tangible: the mentor clicks through it in a browser like a user would.
This follows the roadmap ground rule "The spec is the floor, not the ceiling",
so the frontend is an addition: it never renames or changes anything the spec
defines.

The split at the defense:

- **The web UI is the product for people.** Everything an ordinary user does:
  register, log in, create and edit projects, upload and download documents,
  invite people, send an email link and open it, delete a project.
- **Swagger (`/docs`) is the technical stand.** It proves that protection lives
  on the server, not in the UI: a participant calling `DELETE /project/<id>`
  directly gets 403, a non-owner invite gets 403, no token / a broken token /
  a token after logout gets 401, bad input gets 422. Hiding a button is not
  security; Swagger shows the server says no anyway.

The demo scenario the UI must support end to end (F6 automates it):

1. Register and log in.
2. Create a project (name, description).
3. Upload a pdf or docx and see the used space (once epic 7a provides it).
4. Invite a second user by login.
5. Log in as that user: the project is there, editable, without "Delete project".
6. Download a document.
7. Send a join link by email and open it in a browser (`GET /join`).
8. As the owner, delete the project; its documents go with it.

## Goals

- A React single-page app for the whole user-facing API, in English.
- The look approved on 2026-11-14 (style B with the holographic accent, see
  [`style.md`](style.md)).
- Shipped as its own Docker image: nginx serves the built app and proxies the
  API under `/api/`, so the browser talks to one origin and the backend needs
  no CORS. The backend app, its image, its tests and its CI stay exactly as
  they are (user, 2026-11-14).
- Tested like the backend: component tests, end-to-end tests in a real browser
  against the real API and Postgres, an automated accessibility gate, all in CI.
- Every screen works at phone width (375 px) as well as desktop (1280 px).

## Non-goals

- Rendering anything the API does not provide: no fake numbers, no stubs
  (see "Used space" below).
- Server-side rendering, a second backend.
- Any frontend code, file or test inside the backend app, its image or its CI
  jobs. The user defends and submits the backend; the frontend sits beside it.
- Two languages. The UI is English only.
- Everything marked "later" or "no" in [Beyond the minimum](#beyond-the-minimum).

## Anti-goals (a failure even if it "works")

- The UI hides a button and the server would allow the action anyway. The UI
  hides what a role cannot do; the server must still refuse it.
- The JWT ends up in `localStorage`, a URL, a log line or a cookie readable by
  scripts.
- Data from the API is inserted as raw HTML (`dangerouslySetInnerHTML`,
  `innerHTML`).
- The page loads scripts, fonts or styles from third-party hosts.
- The course provider's company name appears anywhere in the page, its title,
  `package.json`, or HTTP headers (AWS sandbox rule).
- An action fails silently: every error the API can return has a visible,
  plain-English message.
- A change renames or changes a spec endpoint.

## Constraints

- **Spec and roadmap rules** ([`docs/PRDs/roadmap.md`](../PRDs/roadmap.md)):
  endpoint names stay exactly as in the spec; additions are proposed, argued and
  decided by the user; rejected and postponed ones are written down.
- **AWS sandbox rules**: `eu-west-1` only, no company name anywhere, only
  self-signed or ACM certificates, everything rebuildable from this repository.
- **Cost strategy**: nothing new in the persistent or ephemeral layer.
- **What to test** (`CLAUDE.md`): tests prove behaviour; tooling is proven by
  commands that run it. No tests that re-read `package.json`, configs or the
  workflow file.
- **Commits** (`CLAUDE.md`): one commit is one vertical slice (a screen or a
  flow with its tests and config), plain-words subject.
- **Workflow**: frontend work goes through the project skill
  `add-frontend-feature` (agreed look before code, Playwright with axe-core,
  frontend security checklist). It reads its stack, style and layout from this
  folder.
- **API facts this plan builds on**:
  - auth (epic 3, merged): `Authorization: Bearer <jwt>`, 1-hour token,
    `POST /logout` revokes all of the user's tokens, 401 carries
    `WWW-Authenticate: Bearer`, 422 bodies never echo submitted values;
  - projects (epic 4, in progress): responses carry `owner {id, login}` and
    `my_role` (`owner` / `participant`); `GET /projects` pages with
    `limit`/`offset`, filters by `role`, has no total count, sorts by newest
    `updated_at`; a participant's delete gets 403, no access gets 404.

## Approaches considered

### Technology

| Option | Trade-off | Decision |
|---|---|---|
| **React + Vite + TypeScript SPA** | Second toolchain (Node, npm). Backend auth unchanged (JWT in a header); the token is not a cookie, so no CSRF. Matches the user's experience and the `add-frontend-feature` skill | **Chosen** (user, 2026-11-14) |
| Same SPA in Vue | Equal technically; React has more testing examples and the skill already names it | Rejected: the user chose React |
| Jinja2 + HTMX rendered by FastAPI | No Node; `GET /join` solved by a cookie. But auth must also read an HttpOnly cookie, which brings CSRF protection; HTML routes inside a JSON API; a library the user does not know; the skill would need rewriting | Rejected |
| Separate static hosting (S3 + CloudFront) | New AWS services and cost in the sandbox, CORS between two origins unless CloudFront also routes the API | Decided later, for the cloud only (see "Serving and deploy") |

### How the frontend is served

| Option | Trade-off | Decision |
|---|---|---|
| **Own container: nginx serves the build and proxies the API under `/api/` (prefix stripped)** | The backend does not change at all; one origin for the browser, so no CORS and the CSP stays `'self'`; the security and cache headers live in nginx config. Cost: a second image and a second compose service | **Chosen** (user, 2026-11-14) |
| Built into the API image, served by FastAPI at `/app/` (the first choice, built once in PR #14) | One image, one service. But frontend code lands in `main.py`, a Node stage in the backend Dockerfile and frontend tests in the backend suite, which the user defends and submits on its own | Rejected (user, 2026-11-14) |
| Two origins: the web app on its own port calls the API directly | No proxy, but the backend needs CORS for the app's origin, and `connect-src` lists another host | Rejected |

### Where the frontend lives

| Option | Trade-off | Decision |
|---|---|---|
| **Same repository: code in `frontend/`, docs in `docs/frontend/`** | End-to-end tests run against the same `docker compose` stack, one repository for the mentor. Cost: two toolchains side by side. The frontend keeps its own Dockerfile, compose file and workflow inside `frontend/` and `.github/workflows/frontend.yml`, so the backend files stay untouched. Frontend work never changes the backend: an API change the UI needs is a separate backend PR, merged first | **Chosen** (user, 2026-11-14) |
| Separate repository | Fits separate teams with separate releases; here it would mean cross-repo image builds or separate hosting, CORS, two PRs merged in the right order | Rejected |

The frontend's plan stays out of the backend roadmap. The backend roadmap gets
one section, "Frontend requests", listing what the UI needs from the API and in
which API epic (user, 2026-11-14).

### Where the JWT lives in the browser

| Option | Trade-off | Decision |
|---|---|---|
| Memory only | Safest: no script can read it later. Every reload (F5) logs the user out, which looks like a bug at the defense | Rejected |
| **`sessionStorage` + a strict Content Security Policy** | Survives a reload, gone when the tab closes. A script injected into the page (XSS) could read it; React escapes data by default, the CSP blocks foreign scripts, the token lives one hour and logout revokes it | **Chosen** (user, 2026-11-14) |
| `localStorage` | Lives forever, same XSS risk; forbidden by the skill | Rejected |
| HttpOnly cookie | Not readable by scripts, but needs backend auth changes and CSRF protection; a `Secure` cookie does not work over plain HTTP (see HTTPS below) | Rejected |

### Style

Three mockups were compared on 2026-11-14 (warm peach cards, strict black and
white, holographic monospace). Chosen: the strict black-and-white layout, with
two accent colours and the holographic gradient as a background for big titles
only. Details in [`style.md`](style.md).

### Claude Design

Not used as a separate tool. The repository is the single source of truth for
the look (`style.md` plus CSS variables in the code); a parallel design system
in Claude Design would drift. The skill still allows bringing a Claude Design
mockup for one complex screen.

## Design

### Stack

| Area | Decision |
|---|---|
| Language | TypeScript, `strict` |
| Framework | React (current major) |
| Build and dev server | Vite; the app lives at the root of its own origin, so the built `index.html` points at `/assets/…`. In development the Vite dev server proxies `/api/…` to `localhost:8000` with the prefix stripped, exactly like nginx, so there is no CORS locally either |
| API base | Every API call goes to `/api/<spec path>` (for example `/api/login`); the API itself keeps the spec paths |
| Routing | React Router at the root of the origin |
| Server data | TanStack Query: caching, loading and error states per request; its "is anything fetching" state drives the global loader. *Builder's call, made in the plan: the alternative was a hand-written fetch hook per screen* |
| Styling | Plain CSS with CSS variables (the tokens in `style.md`) and CSS Modules per component. No Tailwind, no component library. *Planner's call: smallest thing to explain* |
| Fonts | Inter and Space Mono, self-hosted from npm (`@fontsource/*`), never from Google Fonts |
| Lint and format | ESLint (TypeScript and React hooks rules) and Prettier |
| Type check | `tsc --noEmit` |
| Component tests | Vitest + Testing Library, API calls mocked; test what the user sees and does |
| End-to-end tests | Playwright test runner against the real stack from `docker compose`; `@axe-core/playwright` on every page visited, failing on any WCAG 2.1 AA violation |
| Package manager | npm, `package-lock.json` committed, `npm ci` in CI and Docker; Node version pinned in `frontend/.nvmrc` (current Active LTS) |

### Layout

```
frontend/
  package.json, package-lock.json, .nvmrc, vite.config.ts, tsconfig.json
  Dockerfile, nginx/       the web image: Node build stage, then nginx with its config
  compose.yml              adds the `web` service to the root docker-compose.yml
  README.md                how to run, check and test the frontend
  index.html
  src/
    main.tsx              router, QueryClient, providers
    api/                  fetch wrapper (adds the Bearer header, maps errors), one file per API area
    auth/                 token store (sessionStorage), session-expired handling, login/register pages
    projects/  documents/  members/  profile/  join/     one folder per feature: pages, components, tests
    ui/                   shared components: layout, sidebar, loader bar, toasts, dialogs, banners, avatars
    styles/               tokens.css (CSS variables from style.md), global.css
  e2e/                    Playwright tests and axe helper
docs/frontend/            this design, roadmap, style, mockups, later per-epic specs in specs/
```

Component tests sit next to the component (`*.test.tsx`).

### Serving and deploy

- `frontend/Dockerfile` builds the app in a Node stage (`npm ci`, `npm run
  build`) and copies only `dist` into an nginx image that runs as a non-root
  user. Node does not reach the runtime image.
- The backend stays as it is on `main`: no route, setting, test or Dockerfile
  stage for the frontend. The root `.dockerignore` gets one line, `frontend/`,
  so the backend image never contains frontend files.
- nginx serves the app at the root of its own origin:
  - `/api/…` is proxied to the API with the `/api` prefix stripped
    (`/api/login` → `POST /login` on the API). The browser sees one origin, so
    the backend needs no CORS and `connect-src 'self'` covers the API;
  - files under `/assets/` (the hashed bundles, fonts, icons) are served with
    `Cache-Control: public, max-age=31536000, immutable`; any other file
    (`index.html`, `favicon.svg`) with `Cache-Control: no-cache`, because its
    name does not change when its content does;
  - a missing path under `/assets/`, or any missing path with a file
    extension, answers 404. Never `index.html`: after a deploy a browser with an
    old `index.html` asks for old bundle names, and HTML served as a script is
    refused (`nosniff`), leaving a blank page;
  - every other path returns `index.html` with `Cache-Control: no-cache`, so
    deep links such as `/projects/<id>` survive a reload and a new deploy is
    picked up at once.
- Every response from nginx carries the security headers:
  - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`;
  - `Referrer-Policy: no-referrer` (the join page carries a token in its URL);
  - `X-Content-Type-Options: nosniff`.

  Swagger stays on the API's own port (`/docs`), untouched by this policy: it
  loads its files from a CDN and would break under it.
- Locally `frontend/compose.yml` adds a `web` service to the root
  `docker-compose.yml`, which stays unchanged:
  `docker compose -f docker-compose.yml -f frontend/compose.yml up`.
- Cloud hosting of the frontend is decided later, in a frontend epic of its
  own: an S3 static site (with CloudFront routing `/api/` to the ALB, or CORS)
  or a second container next to the API. Either way it does not touch the
  backend epics 8a and 8b.

### Auth in the browser

- Log in with `POST /login`; keep `access_token` in `sessionStorage`; send it as
  `Authorization: Bearer` from the one fetch wrapper.
- Any 401 from an API call other than `/login`: clear the token, go to
  `/login?next=<current path>`, show "Your session expired. Log in again."
  After login, return to `next` (only a path on the app's own origin that
  starts with a single `/`, never another host).
- Log out calls `POST /logout`, then clears the token, whatever the response.
- Every page except login, register and the join landing needs a token;
  without one it goes to the login page.

### Errors and states

- Every screen has four states: loading, empty, error, success.
- 422 comes in two shapes, and the error mapper handles both:
  - a list of field errors (pydantic validation): each is shown next to its
    field;
  - a single string, for example `{"detail": "Password must not equal the
    login"}` from registration and password change, or the project validation
    messages from epic 4: shown as a message for the whole form.

  The form also validates the same rules before sending (login 3–32 characters
  of `A–Z a–z 0–9 _ . -`, password 8–128, repeat must match, project name
  1–100, description up to 2000).
- 401: session expired flow above. 403: "You don't have permission to do
  this." 404: a "not found" page with a link back to projects. 409: the API's
  `detail` text (for example "Login 'mila' is already taken"). Network down or
  500: "Something went wrong. Try again." with a retry button.
- Global loader: a thin bar at the top of the window while any request is in
  flight; the pressed button shows a spinner and ignores repeat clicks;
  skeleton rows while a list loads for the first time.
- Toasts confirm finished actions: "Project created", "File uploaded",
  "Invite sent", "Link sent".

### Screens

| Screen | API | Notes |
|---|---|---|
| Register, Log in | `POST /auth`, `POST /login` | holographic panel left, form right (mockup screen 3) |
| Profile | `GET /users/me`, `PUT /users/me/password`, `POST /logout`, avatar picker | the password change returns a fresh token: store it |
| Projects list | `GET /projects?role=&limit=&offset=` | tabs All / Owned / Shared with me; "Show more" asks for `limit + 1` to know if there is a next page; empty state "Create your first project" |
| Create / edit project | `POST /projects`, `PUT /project/<id>/info` | dialog or inline form |
| Project page | `GET /project/<id>/info`, documents, members | holographic header with the project name (mockup screen 2); "Delete project" only when `my_role == "owner"`, with a confirmation dialog |
| Documents | `GET/POST /project/<id>/documents`, `GET/PUT/DELETE /document/<id>` | drag and drop or file picker, pdf and docx only; delete with confirmation |
| Members and invite | `GET /project/<id>/members` (accepted in epic 4), `POST /project/<id>/invite?user=<login>` | invite form only for the owner |
| Share by email | `GET /project/<id>/share?with=<email>` | owner only (as the invite) unless epic 10 decides otherwise |
| Join landing | `GET /join` | see below |
| Not found | — | for unknown paths |

### Avatars

- 8–12 light SVG icons in the frontend code: geometric shapes in the
  holographic colours, each with a stable name (for example `orbit-3`).
- The choice is stored on the server so other users see it: a nullable
  `users.avatar` column holding the icon name only (never a file), a migration,
  both repository backends, and `PATCH /users/me` that accepts only the known
  names (422 otherwise). This is a separate backend task, built with the
  `add-feature` skill in its own session, branch and PR, after epic 4 is merged
  (epic 4 adds migration `0003` and the `owner` object, so running both at once
  would give Alembic two heads and conflicting edits). It is merged before F1b;
  F1b only uses the API.
- With no choice stored, the frontend derives an icon from the user id, so
  everyone sees the same default everywhere.
- Uploading one's own picture (S3) is a future improvement, see the roadmap.

### Used space

The bar "18 of 50 MB" appears only when the API returns the project's used and
limit values, which epic 7a adds. Before that the bar is not rendered at all:
no stub, no fake numbers. The size of each document is shown as soon as epic 6
returns it.

### `GET /join` in a browser (proposal for epic 10)

The roadmap left open how a browser user authenticates on `GET /join`: a
clicked link carries no `Authorization` header. With this frontend:

- With the web container in front, the email can contain
  `https://<web host>/join?token=<invite token>`: nginx serves the app's join
  page, and the API needs no content negotiation.
- The join page reads the token, removes it from the address bar
  (`history.replaceState`), asks the user to log in or register if needed
  (keeping the token in memory), then calls the spec's `GET /join?token=…`
  (through the proxy: `/api/join?token=…`) with the Bearer header and opens the
  project it returns.
- Alternative for epic 10 to weigh: the email links to the API's own
  `GET /join`, which answers a browser without an `Authorization` header
  (the request asks for `text/html`) with `303 See Other` to the web app's
  `/join?token=<token>`.

The invite token is not the JWT; the rule "never a JWT in a URL" still holds.
Epic 10 makes the final decision.

### Downloads and uploads

- `GET /document/<id>` needs the Bearer header, so a plain `<a href>` cannot
  download. If epic 6 serves the file through the API, the frontend fetches it
  with the header and saves the blob; if epic 6 returns a presigned S3 URL, the
  browser follows that URL. The frontend follows whatever epic 6 decides.
- If epic 6 chooses direct browser uploads to S3 with presigned URLs, two things
  change: the bucket needs a CORS rule for the app's origin (Terraform, epic 8a),
  and the bucket's origin must be added to the CSP `connect-src`, which is
  `'self'` only. Uploads through the API need neither.

### HTTPS

The sandbox allows only self-signed or ACM certificates; ACM needs a domain we
control, the ALB's own `…elb.amazonaws.com` name cannot get one. Without HTTPS,
passwords and tokens travel in plain text (for Swagger too). Epic 8a decides:
own domain with ACM, self-signed (browser warning), or HTTP for the demo only.
The frontend works either way: `sessionStorage` works over HTTP; the UI does not
rely on APIs that need a secure context (`navigator.clipboard`,
`crypto.randomUUID`).

### CI

- Its own workflow, `.github/workflows/frontend.yml`, runs only when
  `frontend/**` or the workflow itself changes. The backend workflow `ci.yml`
  and its required checks `checks` and `docker` stay backend-only.
- Job `frontend`: `npm ci`, lint, type check, component tests, production
  build, `npm audit --audit-level=high`.
- Job `e2e`: start the stack with both compose files (with a generated
  `APP_JWT_SECRET`), building the API and the web image, run Playwright with
  the axe checks, upload the Playwright report on failure.
- A path-filtered workflow does not start on a backend-only PR, so a required
  check named `frontend` or `e2e` would wait forever there. These two jobs must
  therefore not be required checks in `protect-main`.

## Beyond the minimum

Proposed on 2026-11-14; the user's decisions:

| Addition | Decision | Reason |
|---|---|---|
| Confirmation dialog before deleting a project or a document | **Accepted** | One click must not destroy data |
| "Session expired" on 401 and back to login | **Accepted** | The token lives one hour and can expire mid-demo |
| Toasts for finished actions | **Accepted** | Shows the action worked |
| Drag-and-drop upload | **Accepted** | Expected, looks good in the demo |
| Profile page: change password, log out | **Accepted** | The endpoints exist since epic 3 |
| Phone layout (375 px) | **Accepted** | The mentor may open it on a phone; the skill checks this width anyway |
| Global loader (top bar, button spinners, skeleton rows) | **Accepted** (user's addition) | No screen looks frozen |
| Preset avatars stored on the server | **Accepted** (user's addition) | Other users see them; no file upload needed |
| Tabs All / Owned / Shared with me | **Accepted** (planner's call, free) | The API already filters by `role` |
| Search in the projects list | **Later** | Useful with many projects; client-side only |
| Upload progress bar | **Later** | Needs `XMLHttpRequest` instead of `fetch` |
| Dark theme | **Later** | Doubles the checks, including holographic contrast |
| Uploading one's own avatar picture | **Later** | Needs S3 upload and image checks |
| Account deletion screen | **Later** | `DELETE /users/me` is planned after epic 6; see the roadmap |
| Summary counters (projects, documents, space) above the list | **Later** | `GET /projects` has no totals; would need an API field |
| PDF preview in the browser | **Rejected** | Medium cost, impossible for docx |
| Two UI languages | **Rejected** | English only |

## Acceptance criteria for the plan as a whole

Each frontend epic writes its own criteria through `add-frontend-feature`.
Across all of them:

1. Every spec endpoint keeps its path, method and behaviour.
2. Every user flow in the demo scenario has a Playwright test against the real
   stack, and every page it visits passes the axe check (WCAG 2.1 AA).
3. Every screen has its loading, empty, error and success states covered by
   component tests.
4. The JWT is only ever in `sessionStorage` and in the `Authorization` header.
5. Responses from the web container carry the CSP and the other headers
   above; the browser console shows no CSP violations in the end-to-end runs.
6. No backend file changes for the frontend: the backend app, its image, its
   tests and `ci.yml` stay as they are.
7. Screens are checked at 1280 px and 375 px.
8. `npm audit --audit-level=high` reports nothing open; the lockfile is
   committed.
9. CI jobs `frontend` and `e2e` are green on every PR that touches the
   frontend.

## Left to the builder

- Exact component, hook and file names inside the layout above.
- How the members panel and invite form are arranged on a phone.
- The icon set for the UI (any open-source set installed from npm, no CDN).
- Whether API types are written by hand or generated from FastAPI's
  `/openapi.json` (for example with `openapi-typescript`); if generated, CI
  checks they are up to date.
