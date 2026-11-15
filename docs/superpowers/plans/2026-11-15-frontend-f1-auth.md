# Frontend F1 — Sign in and profile: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register, log in, log out, session expiry on 401, guarded routes and a profile page with password change in the React app.

**Architecture:** A token store (`sessionStorage`, one key) is the only owner of the JWT; one `apiFetch` wrapper adds `/api` and the Bearer header and ends the session on a 401; a `RequireAuth` layout route guards every page except `/login` and `/register`; the current user comes from TanStack Query `["me"]`. Mutations store tokens themselves and resolve with nothing.

**Tech Stack:** React 19, React Router 8, TanStack Query 5, TypeScript strict, CSS Modules, Vitest + Testing Library, Playwright + `@axe-core/playwright`.

**Spec:** [`docs/frontend/specs/2026-11-15-f1-auth-design.md`](../../frontend/specs/2026-11-15-f1-auth-design.md) (read it with this plan; texts and rules are copied from it).

## Global Constraints

- Change only `frontend/`, `docs/frontend/`, `docs/superpowers/plans/` and `.github/workflows/frontend.yml`. Never `src/`, `tests/`, migrations, `pyproject.toml`, `poetry.lock`, root `Dockerfile`, `docker-compose.yml`, `ci.yml`.
- The JWT lives only in `sessionStorage` key `project-hub.token` and the `Authorization` header. Never `localStorage`, a URL, a log line, the query cache.
- No `dangerouslySetInnerHTML`/`innerHTML`. No requests to other origins. No new runtime dependencies.
- UI copy is exactly as in the spec (sentence case, no "please", no "successfully", no "!").
- No comments or docstrings unless the code looks safe to change but is not (`CLAUDE.md` "Comments"); check each diff for new `//`, `/*` and `{/*` lines before committing.
- One commit per task (a vertical slice), plain-words imperative subject ≤ 70 chars, 1–3 line body, **no `Co-Authored-By` trailer**.
- Tests prove behaviour: component tests assert what the user sees (roles, labels, text) and the requests sent; no snapshots, no tests of `src/test/` helpers.
- Every Playwright page visit in a new test runs `expectAccessible(page)` in the state under test.
- Checks per task: `npm run lint`, `npm run typecheck`, `npm test` in `frontend/`; e2e against the stack (see "Running e2e locally").

## Running e2e locally

The stack runs under project name `f1auth` on free ports (other sessions use the defaults):

```bash
# repository root
APP_DB_PORT=55441 APP_PORT=8011 WEB_PORT=8091 APP_JWT_SECRET=$(openssl rand -hex 32) \
  docker compose -p f1auth -f docker-compose.yml -f frontend/compose.yml up -d --build --wait
# frontend/
E2E_BASE_URL=http://127.0.0.1:8091 npx playwright test
```

Rebuild the `web` image (same command) after changing `frontend/src`.

## Review Focus

1. A stale request with the old token returns 401 after a password change stored the new token → the new token stays (Task 6 test).
2. `next` holding `//evil.example`, `/\evil`, `https://…`, `/login` → lands on `/` (Task 1 test).
3. A reload after logout or password change in an e2e test whose page was seeded by `signIn` → the old token is not written back (Tasks 1, 4, 6 e2e).
4. The API is down while logging in or registering → "Something went wrong. Try again." and the button works again (Tasks 1, 2 tests).
5. A double click on a submit button → one request (Task 1 test on `Button busy`).

---

### Task 1: Log in from the login page; every other page needs a login

**Files:**
- Create: `src/auth/tokenStore.ts`, `src/auth/safeNext.ts`, `src/auth/session.ts`, `src/auth/RequireAuth.tsx`, `src/auth/AuthLayout.tsx` + `.module.css`, `src/auth/LoginPage.tsx` + `.module.css`, `src/api/client.ts`, `src/api/errors.ts`, `src/api/auth.ts`, `src/ui/Button.tsx` + `.module.css`, `src/ui/Field.tsx` + `.module.css`, `src/ui/PasswordField.tsx`, `src/test/mockApi.ts`, `e2e/auth.ts`, `e2e/login.spec.ts`
- Modify: `src/routes.tsx`, `src/api/queryClient.ts`, `src/test/setup.ts`, `src/test/renderApp.tsx`, `src/styles/tokens.css`, `src/ui/NotFoundPage.tsx` + `.module.css` (use the shared primary button class), `e2e/fixtures.ts`, `e2e/shell.spec.ts`, `frontend/README.md` (one paragraph: e2e helpers `createUser`/`signIn`, the `f1auth` local stack)
- Test: `src/auth/tokenStore.test.ts`, `src/auth/safeNext.test.ts`, `src/api/client.test.ts`, `src/api/errors.test.ts`, `src/auth/LoginPage.test.tsx`, `src/auth/RequireAuth.test.tsx`, `src/ui/PasswordField.test.tsx`; existing F0 tests keep passing with a token

**Interfaces (produced, used by every later task and by F2):**

```ts
// src/auth/tokenStore.ts
export type EndReason = "expired" | "logout";
export function getToken(): string | null;
export function setToken(token: string): void;          // also forgets the end reason
export function clearToken(reason: EndReason): void;    // removes the key, keeps reason in memory, notifies
export function getEndReason(): EndReason | null;
export function subscribe(listener: () => void): () => void;
export function useToken(): string | null;              // useSyncExternalStore

// src/api/errors.ts
export type FieldError = { loc: (string | number)[]; msg: string; type: string };
export class ApiError extends Error { status: number; detail: string | FieldError[] | null }
export function fieldErrors(error: ApiError): { fields: Record<string, string>; form: string | null };
export function messageFor(error: unknown): string;     // 403/404/0/5xx texts from the parent design

// src/api/client.ts
export function apiFetch<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T>;

// src/api/auth.ts
export type TokenResponse = { access_token: string; token_type: "bearer"; expires_in: number };
export type User = { id: string; login: string; created_at: string };
export function postLogin(body: { login: string; password: string }): Promise<TokenResponse>;
export function getMe(): Promise<User>;

// src/auth/session.ts
export function logIn(login: string, password: string): Promise<void>;  // postLogin + setToken

// src/auth/safeNext.ts
export function safeNext(next: string | null): string;

// src/ui
export function Button(props: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger"; busy?: boolean; wide?: boolean }): JSX.Element;
export function Field(props: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string }): JSX.Element; // forwards ref
export function PasswordField(props: same as Field without type): JSX.Element;

// src/test
export function mockApi(routes: Record<string, { status: number; body?: unknown } | (() => never)>): Mock; // key "POST /api/login"; unknown route fails the test
export function renderApp(path: string, options?: { token?: string | null }): RenderResult; // default token "test-token"

// e2e/auth.ts
export type TestUser = { login: string; password: string };
export function createUser(request: APIRequestContext): Promise<TestUser>;
export function apiToken(request: APIRequestContext, user: TestUser): Promise<string>;
export function signIn(page: Page, request: APIRequestContext, user?: TestUser): Promise<TestUser>;
// e2e/fixtures.ts: new option `expectedApiStatuses: number[]` (default []), set with test.use(...)
```

- [ ] **Step 1: Write the failing unit tests**

  - `tokenStore.test.ts`: `setToken("a")` → `getToken()` is `"a"` and `sessionStorage.getItem("project-hub.token")` is `"a"`, nothing in `localStorage`; `clearToken("expired")` → `getToken()` null, `getEndReason()` `"expired"`, subscriber called; `setToken("b")` → `getEndReason()` null.
  - `safeNext.test.ts`: `"/profile?x=1"` → same; `null`, `""`, `"//evil.example"`, `"/\\evil"`, `"https://evil.example"`, `"profile"`, `"/login"`, `"/login?next=/x"`, `"/register"` → `"/"`.
  - `client.test.ts`: `apiFetch("/users/me")` calls `/api/users/me`; with a token sends `Authorization: Bearer <t>`, without a token sends none; JSON body gets `Content-Type: application/json`; 204 resolves `undefined`; 409 `{detail:"Login 'x' is already taken"}` rejects `ApiError` status 409 with that detail; a `fetch` rejection rejects `ApiError` status 0.
  - `errors.test.ts`: list `[{loc:["body","login"],msg:"String should have at least 3 characters"}]` → `fields.login`; `[{loc:["body"],msg:"Value error, Passwords do not match"}]` → `form` `"Passwords do not match"`; string detail → `form`; `messageFor(ApiError 0)` and 500 → `"Something went wrong. Try again."`, 403 → `"You don't have permission to do this."`.
  - `PasswordField.test.tsx`: the input has type `password`; clicking button "Show password" (`aria-pressed="false"`) makes it `text` and `aria-pressed="true"`; again hides it.

- [ ] **Step 2: Write the failing page tests** (`renderApp` + `mockApi`)

  - `RequireAuth.test.tsx`: `renderApp("/no-such-page?x=1", { token: null })` → heading "Log in"; after logging in (mock `POST /api/login` 200) the heading "Page not found" shows. `renderApp("/")` with a token → heading "Your projects".
  - `LoginPage.test.tsx`:
    - empty submit → "Enter your login" and "Enter your password" next to the fields, no request, focus on Login;
    - 401 → alert "Wrong login or password. Try again.";
    - `POST /api/login` rejecting (network) → alert "Something went wrong. Try again.", button enabled again;
    - success with `/login?next=/no-such-page` → token stored, "Page not found" shown; with `next=//evil.example` → "Your projects";
    - while the request is pending the button "Log in" has `aria-busy="true"` and a second click sends no second request;
    - link "Create one" points to `/register` and keeps `next`;
    - with a token, `/login` shows "Your projects".
  - Existing F0 tests: unchanged assertions; `renderApp` signs in by default.

- [ ] **Step 3: Run `npm test` — the new tests fail (modules missing), F0 tests still pass after the `renderApp` change**

- [ ] **Step 4: Implement**

  - `tokenStore.ts` as in Interfaces; key `project-hub.token`; reason in a module variable.
  - `apiFetch`: `fetch("/api" + path, { method, headers, body: JSON.stringify(body) })`; parse JSON when the body is non-empty; non-2xx → `ApiError(status, body?.detail ?? null)`. (The 401 rule comes in Task 3.)
  - `queryClient.ts`: queries `retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 1`, `refetchOnWindowFocus: false`; mutations `retry: false` (kept).
  - `routes.tsx`: `/login` → `AuthLayout` + `LoginPage`; `RequireAuth` (renders `<Layout />`, or `<Navigate to={"/login?next=" + encodeURIComponent(pathname + search)} replace state={{ reason: getEndReason() }} />`) wraps the F0 children (`/`, `*`).
  - `LoginPage`: fields "Login", "Password"; `useMutation({ mutationFn: () => logIn(login, password) })`; when `useToken()` is set, `<Navigate to={safeNext(next)} replace />`; status/alert messages above the fields per spec; focus the first invalid field on a failed submit.
  - `AuthLayout`: mockup screen 3 (panel: logo, tag `PROJECT_HUB`, `h2`-sized Space Mono text "Your team's projects and documents" (as a `p`, the page `h1` is the form heading), "Create projects, upload files, invite people."); phone layout per spec.
  - `Button`: `busy` → `aria-busy="true"`, spinner icon (`LoaderCircle`, `aria-hidden`), click ignored. Tokens added to `tokens.css`: `--color-ink-hover: #2b2b30`, `--text-button: 13px`, `--button-padding: 8px 14px`.
  - `Field`: `<label htmlFor>`, `aria-invalid`, `aria-describedby` → hint and error ids (`useId`).
  - `PasswordField`: toggle inside the field, visible text always "Show" (a changing visible text would no longer match the accessible name, WCAG 2.5.3), `aria-label="Show password"`, `aria-pressed`, a visible pressed style (for example underlined), ≥ 32 px tall.
  - `mockApi`: `vi.stubGlobal("fetch", …)`; `setup.ts` afterEach: `vi.unstubAllGlobals()`, `setToken("")`, `sessionStorage.clear()`.

- [ ] **Step 5: Write the e2e tests and helpers**

  - `e2e/auth.ts`: `createUser` posts `/api/auth` with a unique login (`"e2e" + Date.now().toString(36) + random base36`, ≤ 32 chars) and password `"pw-" + randomUUID()`; `apiToken` posts `/api/login`; `signIn` gets a token and calls `page.addInitScript` that writes `project-hub.token` only if `sessionStorage` has no `project-hub.e2e-seeded` key, and then sets that key.
  - `fixtures.ts`: option `expectedApiStatuses`; a console error that starts with "Failed to load resource" for a URL containing `/api/` with one of those statuses is not a problem.
  - `login.spec.ts` (`test.use({ expectedApiStatuses: [401] })` where a wrong password is tried): open `/projects-x` logged out → "Log in" page, axe; wrong password → alert, axe; right password → "Page not found" at `/projects-x`; reload → still there (token kept); `sessionStorage` has only `project-hub.token` with a value, `localStorage` is empty.
  - `shell.spec.ts`: each test calls `signIn(page, request)` before `page.goto`.

- [ ] **Step 6: Run all checks** — `npm run lint && npm run typecheck && npm test` pass; rebuild the stack; `npx playwright test` passes (desktop, phone, http).

- [ ] **Step 7: Commit** — `Log in from the login page; other pages need a login`

---

### Task 2: Create an account and land logged in

**Files:**
- Create: `src/auth/RegisterPage.tsx` (+ `.module.css` if needed), `src/auth/passwordRules.ts`, `e2e/register.spec.ts`
- Modify: `src/api/auth.ts` (`postRegister`), `src/auth/session.ts` (`register`), `src/routes.tsx`, `src/auth/LoginPage.tsx` (state `{ reason: "created", login }` → message "Account created. Log in." and Login prefilled)
- Test: `src/auth/RegisterPage.test.tsx`, `src/auth/passwordRules.test.ts`

**Interfaces:**
- Consumes: Task 1 (`apiFetch`, `fieldErrors`, `messageFor`, `logIn`, `Field`, `PasswordField`, `Button`, `AuthLayout`, `safeNext`, `useToast` from F0).
- Produces:
  ```ts
  export function postRegister(body: { login: string; password: string; repeat_password: string }): Promise<User>;
  export function checkLogin(login: string): string | null;              // "Use 3–32 characters: letters, digits, _ . -"
  export function checkNewPassword(password: string, login: string): string | null;
  // "Use 8–128 characters" | "Use only English letters, digits, keyboard symbols and spaces" | "Password must not equal the login"
  ```
  `checkNewPassword` is reused by Task 6.

- [ ] **Step 0: Toasts ready for their first caller (own commit, before the page)** — carried from the F0 spec ("before the first `useToast()` call"); this task makes the first call. In `src/ui/toast/`: both regions get `aria-atomic="false"` and `aria-relevant="additions"`; a success toast's 5 s timer pauses while the pointer is over it or focus is inside it and restarts (full 5 s) when both leave (WCAG 2.2.1); after a keyboard dismiss the focus goes to the next toast's Dismiss button, or back to the element that had focus before the toast region (fall back to `main`); on phones the wrapper uses `inset-inline: 16px` instead of `left: 50%` + `translateX`. Tests in `Toasts.test.tsx` (fake timers): hover keeps a success toast past 5 s, leaving hides it 5 s later; focus on Dismiss does the same; keyboard dismiss moves focus as described; regions have the two attributes. Commit: `Pause success toasts on hover and focus` (body: announce only new toasts, focus after dismiss, phone centring).
- [ ] **Step 1: Failing tests**
  - `passwordRules.test.ts`: `checkLogin("ab")`, `"a".repeat(33)`, `"mi la"`, `"міла"` → the login message; `"mila_1.x-"` → null. `checkNewPassword("short", "x")` → "Use 8–128 characters"; 129 chars → same; `"пароль123"` → the ASCII message; `"mila1234"` with login `"mila1234"` → "Password must not equal the login"; `"correct horse"` → null.
  - `RegisterPage.test.tsx`: each rule shows its message next to its field and sends nothing; repeat differs → "Passwords do not match"; 409 → "That login is taken. Try another." next to Login; 422 list `loc ["body","login"]` → shown next to Login; success → requests `POST /api/auth` then `POST /api/login` with the same login and password, toast "Account created", heading "Your projects"; success with `next=/no-such-page` → "Page not found"; `POST /api/login` failing after a 201 → "Log in" page with "Account created. Log in." and Login filled; link "Log in" keeps `next`; network down → "Something went wrong. Try again.".
- [ ] **Step 2: Run, see them fail**
- [ ] **Step 3: Implement** — `/register` route under `AuthLayout`; fields "Login" (hint "3–32 characters: letters, digits, _ . -"), "Password" (hint "8–128 characters"), "Repeat password"; button "Create account"; `register()` in `session.ts` = `postRegister` then `logIn`, resolves nothing; on a login failure after 201 navigate to `/login` with state `{ reason: "created", login }`.
- [ ] **Step 4: e2e** `register.spec.ts`: open `/register`, axe; submit mismatched repeat → message, axe; register a unique login → "Your projects", toast "Account created"; register the same login again in a fresh context (`expectedApiStatuses: [409]`) → "That login is taken. Try another.", axe.
- [ ] **Step 5: Checks pass** (lint, typecheck, test, e2e)
- [ ] **Step 6: Commit** — `Create an account and land logged in on the projects page`

---

### Task 3: End the session on a 401 and say so on the login page

**Files:**
- Create: `src/auth/useMe.ts`, `src/auth/SessionCacheReset.tsx` (or the same logic inside `AppProviders`), `e2e/session.spec.ts`
- Modify: `src/api/client.ts`, `src/api/auth.ts` (nothing new), `src/ui/Layout.tsx` (calls `useMe()`), `src/AppProviders.tsx`, `src/auth/LoginPage.tsx`
- Test: `src/api/client.test.ts` (extend), `src/auth/session.test.tsx`

**Interfaces:**
- Produces: `export function useMe(): UseQueryResult<User, ApiError>` (key `["me"]`, `getMe`).
- Behaviour: in `apiFetch`, a 401 on a request that sent token `t` calls `clearToken("expired")` only if `getToken() === t`; a 401 without a token only throws. When the token goes from a value to null, the query client is cleared.

- [ ] **Step 1: Failing tests**
  - `client.test.ts`: 401 with token → token null, reason `"expired"`; 401 with token `"old"` while the store now holds `"new"` → `"new"` stays; 401 without a token → reason unchanged, token unchanged.
  - `session.test.tsx`: `renderApp("/no-such-page")` with `GET /api/users/me` → 401 → heading "Log in", status "Your session expired. Log in again."; logging in again returns to "Page not found"; the query cache holds no `["me"]` after the session ended (assert via a fresh `GET /api/users/me` request after re-login).
- [ ] **Step 2: Run, see them fail**
- [ ] **Step 3: Implement** per Behaviour; `LoginPage` shows the message for `location.state.reason === "expired"` with `role="status"`. `mockApi` answers `GET /api/users/me` with 200 `{ id: "00000000-0000-4000-8000-000000000001", login: "mila", created_at: "2026-11-14T12:00:00Z" }` unless the test's routes define it, so tests that do not care about the user stay short.
- [ ] **Step 4: e2e** `session.spec.ts` (`expectedApiStatuses: [401]`): `signIn`, open `/no-such-page`; revoke via `POST /api/logout` with that token (`request` with the header); `page.reload()` → "Log in" with "Your session expired. Log in again.", axe; log in → back on `/no-such-page`.
- [ ] **Step 5: Checks pass**
- [ ] **Step 6: Commit** — `Send the user back to log in when the session expires`

---

### Task 4: Log out from the sidebar

**Files:**
- Modify: `src/api/auth.ts` (`postLogout`), `src/auth/session.ts` (`logOut`), `src/ui/Layout.tsx` (+ `.module.css`), `src/auth/LoginPage.tsx`
- Create: `e2e/logout.spec.ts`
- Test: `src/ui/Layout.test.tsx` (extend)

**Interfaces:** `export function postLogout(): Promise<void>`; `export function logOut(): Promise<void>` — calls `postLogout`, then `clearToken("logout")` in `finally`, never rejects.

- [ ] **Step 1: Failing tests** (`Layout.test.tsx`): button "Log out" in navigation "Main"; click → `POST /api/logout` sent with the Bearer header, heading "Log in", status "You are logged out.", token null; the same when `POST /api/logout` answers 500 or the network fails; on phone width it is inside the menu (same as Projects).
- [ ] **Step 2: Run, see them fail**
- [ ] **Step 3: Implement** — a `button` styled like the nav links (`LogOut` icon), below the links; busy while the call runs.
- [ ] **Step 4: e2e** `logout.spec.ts`: `signIn`, open `/`, log out (on phone through the menu) → "You are logged out.", axe; `page.reload()` → still "Log in" (the seed script does not bring the token back); `page.goto("/")` → "Log in".
- [ ] **Step 5: Checks pass**
- [ ] **Step 6: Commit** — `Log out from the sidebar`

---

### Task 5: See your profile with your default avatar, and a greeting on projects

**Files:**
- Create: `src/ui/avatar/icons.tsx`, `src/ui/avatar/defaultAvatarName.ts`, `src/ui/avatar/Avatar.tsx` (+ `.module.css`), `src/profile/ProfilePage.tsx` (+ `.module.css`), `e2e/profile.spec.ts`
- Modify: `src/routes.tsx` (`/profile`), `src/ui/Layout.tsx` (nav link "Profile", `UserRound` icon, between Projects and Log out), `src/projects/ProjectsPage.tsx`, `src/ui/Banner.tsx` (optional `aside` slot for the avatar, if needed)
- Test: `src/ui/avatar/defaultAvatarName.test.ts`, `src/profile/ProfilePage.test.tsx`, `src/projects/ProjectsPage.test.tsx` (extend)

**Interfaces:**
```ts
export const avatarNames = ["orbit", "prism", "wave", "grid", "petal", "ring", "stack", "spark", "arc", "tile"] as const;
export type AvatarName = (typeof avatarNames)[number];
export function defaultAvatarName(userId: string): AvatarName; // FNV-1a 32-bit over the UTF-16 code units, unsigned, % 10
export function Avatar(props: { userId: string; size: number }): JSX.Element; // aria-hidden svg, data-avatar={name}
```

- [ ] **Step 1: Failing tests**
  - `defaultAvatarName.test.ts`: same id twice → same name; for the 20 ids `"00000000-0000-4000-8000-0000000000NN"` (NN 00–19) at least 5 different names appear; a pinned expectation for 2 fixed ids (compute once with the implementation, then keep it; it guards against a hash change that would change everyone's avatar).
  - `ProfilePage.test.tsx`: while `GET /api/users/me` is pending → `progressbar` "Loading" visible and no heading yet (skeleton has `aria-hidden`); 200 `{login:"mila", created_at:"2026-11-14T12:00:00Z"}` → heading "mila", text "Member since 14 Nov 2026"; 500 → alert "Something went wrong. Try again." and button "Try again" refetches and shows "mila"; nav link "Profile" has `aria-current="page"`.
  - `ProjectsPage.test.tsx`: with `GET /api/users/me` 200 login "mila" → text "HI, MILA"; while it loads → "PROJECT_HUB"; on 500 → "PROJECT_HUB".
- [ ] **Step 2: Run, see them fail**
- [ ] **Step 3: Implement** — 10 icons, `viewBox="0 0 32 32"`, shapes from the approved mockup (`.superpowers/f1/avatars.js`), colours from the holographic stops, `ink` outlines; round with a 1 px ink border; banner on Profile: avatar 56 px, tag "PROFILE", `h1` login, "Member since …" with `Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" })`.
- [ ] **Step 4: e2e** `profile.spec.ts`: `signIn`, open `/profile` (on phone through the menu from `/`) → heading = the user's login, "Member since", axe.
- [ ] **Step 5: Checks pass**
- [ ] **Step 6: Commit** — `See your profile with a default avatar and a greeting on projects`

---

### Task 6: Change the password from the profile and stay logged in

**Files:**
- Modify: `src/api/auth.ts` (`putPassword`), `src/auth/session.ts` (`changePassword`), `src/profile/ProfilePage.tsx`
- Create: `src/profile/ChangePasswordForm.tsx` (+ `.module.css`), `e2e/password.spec.ts`
- Test: `src/profile/ChangePasswordForm.test.tsx`, `src/api/client.test.ts` (stale 401 case already in Task 3)

**Interfaces:** `export function putPassword(body: { current_password: string; new_password: string; repeat_new_password: string }): Promise<TokenResponse>`; `export function changePassword(current: string, next: string, repeat: string): Promise<void>` — stores the new token, resolves nothing.

- [ ] **Step 1: Failing tests** (`ChangePasswordForm.test.tsx`, rendered through `renderApp("/profile")`):
  empty → "Enter your current password" next to Current password; `checkNewPassword` messages next to New password (login from `useMe`, e.g. new = login → "Password must not equal the login"); repeat differs → "Passwords do not match"; new = current → "New password must differ from the current one"; nothing sent in those cases; 400 → "Current password is wrong. Try again." next to Current password; 422 string → form alert with the text; success → the stored token equals the response's `access_token`, the three fields are empty, toast "Password changed", page still shows "mila"; network down → "Something went wrong. Try again.".
- [ ] **Step 2: Run, see them fail**
- [ ] **Step 3: Implement** — panel `section` with `h2` "Change password", line "Changing the password logs you out on other devices.", three `PasswordField`s (hint "8–128 characters" on New password), primary "Change password" with `busy`.
- [ ] **Step 4: e2e** `password.spec.ts` (`expectedApiStatuses: [400]`): `signIn`, `/profile`; wrong current → message, axe; correct change → toast, axe; `page.reload()` → still on profile; `apiToken` with the old password → 401, with the new → 200.
- [ ] **Step 5: Checks pass**
- [ ] **Step 6: Commit** — `Change the password from the profile and stay logged in`

---

### Task 7: Move the focus to the page heading after navigation

**Files:**
- Create: `src/ui/useFocusHeadingOnNavigate.ts`
- Modify: `src/ui/Layout.tsx`, `src/auth/AuthLayout.tsx`, page `h1`s get `tabIndex={-1}` (Banner `h1`, Log in, Create account)
- Test: `src/ui/Layout.test.tsx` (extend), `e2e/shell.spec.ts` (extend)

**Interfaces:** `export function useFocusHeadingOnNavigate(container: RefObject<HTMLElement | null>): void` — after a `pathname` change (not on first render) focuses the first `h1` inside `container`.

- [ ] **Step 1: Failing tests**: from `/no-such-page` click "Go to projects" → heading "Your projects" has focus; on first render nothing is focused; on phone width choosing "Profile" in the menu focuses heading of the profile once loaded (`findByRole` then `toHaveFocus`); from Log in clicking "Create one" focuses "Create account".
- [ ] **Step 2: Run, see them fail**
- [ ] **Step 3: Implement** (an `h1` that renders later, as on Profile, is focused when it appears: use a `MutationObserver` or re-run on render until found, builder's call; the skip link keeps working).
- [ ] **Step 4: e2e** `shell.spec.ts`: after clicking "Go to projects", the heading is focused.
- [ ] **Step 5: Checks pass**
- [ ] **Step 6: Commit** — `Move the focus to the page heading after navigation`

---

## After the tasks

Phase 6 of `add-frontend-feature` (verification, screenshots, accessibility review, security checklist, the backend-unchanged command), then the PR and `/code-review`.
