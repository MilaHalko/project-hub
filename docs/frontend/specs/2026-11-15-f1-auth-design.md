# F1 — Sign in and profile

Date: 2026-11-15
Status: approved by the user (2026-11-15)
Parent design: [`../2026-11-14-frontend-design.md`](../2026-11-14-frontend-design.md)
Roadmap row: [`../roadmap.md`](../roadmap.md) (F1)
Style: [`../style.md`](../style.md)

## Intent

Let a person use the web app as themselves: register, log in, stay logged in
across a reload, log out, change the password, and be sent back to the login
page when the token runs out mid-demo instead of seeing broken screens. Every
later epic (F2 projects first) builds on the pieces made here: the token store,
the one API client with the Bearer header, the guarded routes and the
end-to-end sign-in helper.

The parent design already decides where the token lives (`sessionStorage`, user,
2026-11-14), the 401 flow, the `next` rule and the error texts; they are not
repeated here unless F1 makes them concrete.

## Goals

- Register, log in and log out from the browser against the real API.
- Every page except `/login` and `/register` needs a token; without one it goes
  to the login page and, after login, back to where the person was.
- Any 401 from the API (other than a wrong password at login) ends the session
  with "Your session expired. Log in again."
- A profile page with the login, the default avatar, the account's creation date
  and a password change form.
- Pieces F2 reuses without changes: `apiFetch` (API client), the token store,
  `useMe()` (current user), the route guard, the form field and button
  components, and the end-to-end helpers that create and sign in a user.

## Non-goals

- Avatar picker and `PATCH /users/me` (F1b; needs a backend task first).
- Display name (proposed backend request, F1b).
- Deleting the account (later; no endpoint).
- A timer that logs out the moment the token's hour is over: the next request's
  401 does it.
- Login brute-force protection (backend, known limitation).
- `/join` (epic 10, F5).

## Anti-goals

Those of the parent design, in particular: the JWT never in `localStorage`, a
URL, a log line, a cookie or the React Query cache; `next` never sends the
browser to another origin; no backend file changes; no raw HTML from data.

## Constraints

API facts (epic 3, merged; read from `src/project_hub/auth/` and `users/`):

| Call | Body | Success | Errors the UI handles |
|---|---|---|---|
| `POST /auth` | `{login, password, repeat_password}` | 201 `{id, login, created_at}` (no token) | 409 `{"detail": "Login 'x' is already taken"}`; 422 list (field rules, and `loc: ["body"]` "Value error, Passwords do not match" / "Value error, Password must not equal the login") |
| `POST /login` | `{login, password}` | 200 `{access_token, token_type: "bearer", expires_in: 3600}` | 401 "Invalid login or password"; 422 list (empty or oversized) |
| `POST /logout` | — (Bearer) | 204; revokes all of the user's tokens | 401 |
| `GET /users/me` | — (Bearer) | 200 `{id, login, created_at}` | 401 |
| `PUT /users/me/password` | `{current_password, new_password, repeat_new_password}` | 200 token response; all older tokens revoked, so the new token must be stored at once | 400 "Current password is incorrect"; 422 string "Password must not equal the login"; 422 list (rules, `loc: ["body"]` "Passwords do not match" / "New password must differ from the current one"); 401 |

Rules the forms check before sending (same as the API): login 3–32 characters
of `A–Z a–z 0–9 _ . -`; password 8–128 printable ASCII characters (letters,
digits, keyboard symbols, space); repeat equals password; password not equal to
the login; new password not equal to the current one.

## Approaches

| Option | Trade-off | Decision |
|---|---|---|
| **Token store module (`sessionStorage` + change subscription) + one `apiFetch` wrapper + guard as a layout route + current user through TanStack Query** | One source of truth for the token, readable from plain functions and from React (`useSyncExternalStore`); F2 just calls `apiFetch`; the guard is one component | **Chosen** (builder's call, the user handed over the how on 2026-11-15) |
| Token in a React context (`AuthProvider`) | API functions live outside React and would need the token passed in, or a second copy of it | Rejected |
| Guard and data in React Router loaders | A second way of loading data next to TanStack Query that F2 would have to follow | Rejected |

## Decisions with the user (2026-11-15)

- After registration the app logs in at once (`POST /auth`, then `POST /login`
  with the same login and password) and opens the projects page. Rejected: going
  to the login page and typing the password again.
- Extras accepted: a "Show password" toggle on every password field; the
  projects banner tag greets the user ("HI, MILA", the login in capitals, as in
  the approved mockup); "Member since 14 Nov 2026" on the profile.

## Design

### Routes

| Path | Access | Page |
|---|---|---|
| `/login` | public; with a token → `/` | Log in |
| `/register` | public; with a token → `/` | Create account |
| `/` | token | Projects (F0 banner; tag "HI, <LOGIN>") |
| `/profile` | token | Profile |
| anything else | token | Not found (F0) |

`/login` and `/register` use an auth layout without the sidebar: holographic
panel left, form right (mockup screen 3); below 768 px the panel becomes a short
holographic block above the form. Guarded pages use the F0 `Layout`, wrapped by
the guard. An unknown path without a token goes to the login page (it is a
guarded route), and after login shows "Page not found".

### Token store (`src/auth/tokenStore.ts`)

- `getToken()`, `setToken(token)`, `clearToken(reason)` and `subscribe(listener)`;
  key `project-hub.token` in `sessionStorage`.
- `clearToken` takes the reason, `"logout"` or `"expired"`, kept in memory only
  (not in storage), so the login page can show the right message once.
- `useToken()` reads it in React with `useSyncExternalStore`.
- Nothing else touches `sessionStorage`.

### API client (`src/api/client.ts`)

- `apiFetch<T>(path, { method, body })`: calls `/api` + `path`, sends JSON, adds
  `Authorization: Bearer <token>` when there is a token, returns the parsed body
  (or nothing for 204).
- Any non-2xx answer throws `ApiError { status, detail }`, where `detail` is the
  string or the field list from the body; a network failure throws `ApiError`
  with status `0`.
- A 401 on a request that carried a token: `clearToken("expired")` before
  throwing, but only if the token it sent is still the stored one (a request
  sent with the old token can come back after a password change has stored the
  new one, and must not wipe it). A 401 on a request without a token (the login
  form) only throws.
- `src/api/errors.ts`: `fieldErrors(error)` turns a 422 list into
  `{ field: message }` by the last `loc` element, strips pydantic's
  "Value error, " prefix, and returns the `loc: ["body"]` messages and string
  details as a form-level message. A generic `messageFor(error)` gives the
  parent design's texts for 403, 404, 0 and 5xx.
- `src/api/auth.ts`: `register`, `login`, `logout`, `getMe`, `changePassword`,
  typed by hand (the API has five auth calls; generating types is left for
  later).
- Query client defaults: no retry for an `ApiError` with a 4xx status (a 401 is
  never retried), at most one retry otherwise; `refetchOnWindowFocus: false`.

### Session lifecycle

- **Guard** (`RequireAuth`, a layout route): no token → `<Navigate>` to
  `/login?next=<path + search>` with the reason (`expired`, `logout` or none)
  in the navigation state. With a token it renders the `Layout`.
- **Current user**: `useMe()` = TanStack Query `["me"]` over `GET /users/me`. The
  `Layout` calls it, so a stale token at start-up gives a 401 and the session
  expired flow at once. If it fails otherwise (network down, 5xx), pages that
  only decorate with the user (the projects greeting) render as if it were
  still loading; only Profile, which needs the user, shows the error with "Try
  again" (builder's call).
- **The token never enters the query cache**: the login, register and
  password-change mutations store the token themselves (`setToken`) and resolve
  with nothing, so TanStack's mutation cache never holds it.
- **Log in**: on success `setToken`, then navigate to `safeNext(next)`.
  `safeNext` accepts only a value that starts with one `/` and not `//` or `/\`,
  and is not `/login` or `/register`; otherwise `/`.
- **Session ended** (logout or 401): the query cache is cleared
  (`queryClient.clear()`), so the next user never sees the previous one's data.
- **Log out**: a "Log out" button in the sidebar (below Profile). It calls
  `POST /logout`, then `clearToken("logout")` whatever the answer; the login
  page says "You are logged out." No toast.
- **Password change**: on success the new token replaces the old one, the form
  is emptied and a toast says "Password changed". The person stays logged in.

### Screens and states

**Log in** (`/login`): heading "Log in", line "No account? Create one" (link to
`/register`, keeping `next`), fields Login and Password (with Show password),
primary button "Log in" (full width).
- Messages sit above the fields, below the "No account?" line, one at a time:
  "Your session expired. Log in again." (reason `expired`), "You are logged
  out." (reason `logout`) or "Account created. Log in." (see Create account),
  `role="status"`; a form error replaces them.
- Empty fields: "Enter your login" / "Enter your password" next to the field.
- 401: "Wrong login or password. Try again." above the fields (`role="alert"`).
- 0 / 5xx: "Something went wrong. Try again."
- Busy: the button shows a spinner and ignores repeat clicks.

**Create account** (`/register`): heading "Create account", line "Have an
account? Log in", fields Login (hint "3–32 characters: letters, digits, _ . -"),
Password (hint "8–128 characters"), Repeat password, primary "Create account".
- Client checks as listed under Constraints, each next to its field: "Use 3–32
  characters: letters, digits, _ . -", "Use 8–128 characters", "Use only English
  letters, digits, keyboard symbols and spaces", "Passwords do not match",
  "Password must not equal the login".
- 409: "That login is taken. Try another." next to Login.
- 422 from the API: mapped by `fieldErrors`.
- Success: log in at once, toast "Account created", open `safeNext(next)`. If
  that login fails, go to the login page with the login filled in and the
  message "Account created. Log in." (the account exists; builder's call).

**Projects** (`/`, F0 page): the banner tag is "HI, <LOGIN>" once `useMe()` has
the user, "PROJECT_HUB" while it loads. The rest stays as in F0 until F2.

**Profile** (`/profile`): banner with tag "PROFILE", the avatar (56 px), the
login as the title and "Member since 14 Nov 2026" (`created_at`, `en-GB` day,
short month, year, in the browser's time zone). Below, a panel "Change
password": Current password, New password (hint "8–128 characters"), Repeat
new password, a line "Changing the password logs you out on other devices."
and the primary button "Change password".
- Loading: a skeleton banner. Error (0 / 5xx): "Something went wrong. Try
  again." with a "Try again" button. 401: session expired flow.
- Client checks: required current password ("Enter your current password"),
  the password rules, "Passwords do not match", "New password must differ from
  the current one", "Password must not equal the login".
- 400: "Current password is wrong. Try again." next to Current password.
- Success: see Session lifecycle.

**Sidebar** (F0 `Layout`): nav Projects, Profile, and a "Log out" button styled
like a nav item. On phones they are in the menu, as in F0.

### Avatars (`src/ui/avatar/`)

- 10 geometric icons drawn as inline SVG React components in the holographic
  colours, each with a stable name (`orbit`, `prism`, `wave`, `grid`, `petal`,
  `ring`, `stack`, `spark`, `arc`, `tile`; exact shapes are the builder's call).
  F1b will offer the same set in the picker and store the name.
- `defaultAvatarName(userId)`: FNV-1a hash of the id string, modulo the number
  of icons, so every browser shows the same default for the same user.
- `<Avatar userId size />`: round, decorative (`aria-hidden`) because the login
  is always shown next to it. F1b adds an optional stored name.

### Shared UI (carried from F0)

- Button tokens instead of hard-coded values: hover colour, button text size
  (13 px), button padding; a `Button` component with variants primary,
  secondary, danger and a `busy` state (spinner, `aria-busy`, ignores clicks).
  The F0 not-found link uses the same primary class.
- `Field` (label, input, hint, error with `aria-invalid` and
  `aria-describedby`) and `PasswordField` (adds a toggle inside the field:
  visible text "Show", accessible name "Show password", `aria-pressed`; at least
  32 px tall for touch). On a failed submit the first invalid field gets the focus.
- Focus on navigation: after a route change (not on first load) the focus moves
  to the page's `h1`, which also fixes the focus loss after choosing a phone
  menu item (carried from F0).

### Tests

Component tests (Vitest + Testing Library; `fetch` stubbed by a small helper in
`src/test/`):

- `apiFetch`: `/api` prefix, Bearer header when a token exists, `ApiError` for
  non-2xx and network failure, a 401 with a token clears it with reason
  `expired`, a 401 without a token does not.
- `fieldErrors`: both 422 shapes and the `loc: ["body"]` case.
- `safeNext`: accepts `/profile?x=1`; rejects `//evil.example`, `/\evil`,
  `https://evil.example`, `/login`, empty.
- Guard: no token → login page, `next` kept; token → page.
- Log in, Create account, Profile, sidebar Log out: every state listed above.
- Projects: greeting from `GET /users/me`.
- `defaultAvatarName`: same id → same name; known ids give known names.
- F0 tests that open guarded pages get a token first.

End-to-end (Playwright against the composed stack, desktop and phone, axe on
every page visited, in its states with messages shown):

- Helpers in `e2e/auth.ts`: `createUser(request)` registers a unique login via
  `POST /api/auth` and returns login and password; `signIn(page, request,
  user)` gets a token via `POST /api/login` and puts it in `sessionStorage`
  before the app starts. The token is written once (the init script writes it
  only while the key is absent), so a reload after a logout or a password
  change does not bring an old token back. F2 uses both.
- The fixture's "no console errors" rule gets an opt-in list of expected API
  statuses per test (Chromium logs every 4xx response as a console error).
- Flows: register and land on projects with the greeting; wrong password, then
  log in; open `/profile` logged out, log in, land on `/profile`; session
  expired (token revoked through the API, then reload) and back after login;
  log out and the guard holds after it; change the password (wrong current
  first), stay logged in after a reload, the old password no longer logs in.
- F0 shell tests sign in first.

## Acceptance criteria

| # | Given / when / then | Proven by |
|---|---|---|
| 1 | Given no account, when I fill Create account correctly, then I am logged in on the projects page, see "HI, <LOGIN>" and a toast "Account created" | Vitest + Playwright |
| 2 | When I break a registration rule, I see its message next to the field and nothing is sent | Vitest |
| 3 | When the login is taken, I see "That login is taken. Try another." | Vitest |
| 4 | Given an account, when I log in, I land on `next` (safe) or `/` | Vitest + Playwright |
| 5 | When the password is wrong, I see "Wrong login or password. Try again." | Vitest + Playwright |
| 6 | Given no token, when I open a guarded page, I get the login page and return to that page after login | Vitest + Playwright |
| 7 | `next` never leaves the app's origin and never points at `/login` or `/register` | Vitest |
| 8 | Given a revoked or expired token, when the app gets a 401, the token is gone and the login page says "Your session expired. Log in again." | Vitest + Playwright |
| 9 | When I log out, `POST /logout` is called, the token is gone even if the call fails, and the login page says "You are logged out." | Vitest + Playwright |
| 10 | The token survives a reload in the same tab and is only in `sessionStorage` under one key | Playwright |
| 11 | The profile shows the login, the default avatar and "Member since <date>"; loading and error states work | Vitest |
| 12 | Password change: rules next to fields, 400 next to Current password, success stores the new token, empties the form, toasts "Password changed"; the old password stops working | Vitest + Playwright |
| 13 | The same user id always gets the same default avatar | Vitest |
| 14 | Show password reveals and hides the password | Vitest |
| 15 | After a route change the focus is on the page heading | Vitest |
| 16 | Every page visited passes axe (WCAG 2.1 AA) at 1280 and 375 px; no unexpected console errors; no request to another origin | Playwright |
| 17 | No backend file changes: `git diff origin/main --stat -- src tests migrations pyproject.toml poetry.lock Dockerfile docker-compose.yml .github/workflows/ci.yml` is empty | the command |
| 18 | Lint, type check, component tests, build, audit pass; CI `checks`, `docker`, `frontend`, `e2e` green | the commands, GitHub |

## Left to the builder

File and component names inside the layout above, the icon shapes, the spinner,
the skeleton, and how `fetch` is stubbed in component tests.

## Look

Mockups approved on 2026-11-15 (thrown away after F1, not committed):
`.superpowers/f1/` (log in, create account, profile with the password panel and
the ten default avatars, projects greeting; 1280 and 375 px). Design critique
changes: form errors sit above the fields, where the status messages are, so
the eye finds every form-level message in one place; the Show toggle got a
32 px touch target.
