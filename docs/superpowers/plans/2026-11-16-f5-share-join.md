# F5 Share and Join Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (Native, chosen in `add-frontend-feature`). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner mails a join link from the project page; whoever opens it signs in, clicks "Join project" and lands in the project as a participant.

**Architecture:** Two thin API functions in `src/api/shares.ts`. A `ShareForm` in the members panel. A `/join` route whose outer element moves `?token=` into `sessionStorage` and cleans the address before the usual `RequireAuth` guard runs, and a `JoinPage` that calls the API once per click. nginx logs paths without query strings; `frontend/compose.yml` gives the API `APP_WEB_URL`.

**Tech Stack:** React 19, React Router 8, TanStack Query 5, Vitest + Testing Library, Playwright + `@axe-core/playwright`, nginx, docker compose, Mailpit HTTP API.

**Spec:** [`docs/frontend/specs/2026-11-16-f5-share-join-design.md`](../../frontend/specs/2026-11-16-f5-share-join-design.md)

## Global Constraints

- Only `frontend/`, `docs/frontend/`, `docs/superpowers/plans/`, `.github/workflows/frontend.yml` change. No backend file.
- Copy exactly as in the spec ("Design" section); sentence case, no "please", "successfully" or "!".
- The join token never goes into a URL the app builds after landing, except the API call `/api/join?token=…`.
- The JWT stays where F1 put it; the join token lives in `sessionStorage` key `project-hub.join-token`.
- No comments or docstrings unless they guard a hidden reason. No `Co-Authored-By` trailer.
- Every e2e page visit ends with `expectAccessible(page)`; tests that expect a 4xx add `test.use({ expectedApiStatuses: [...] })`.
- Test emails use `example.com`.

## Review Focus

1. Double click or Enter twice on "Join project" → exactly one `GET /api/join` (a second call answers 404 after a success). Test in Task 2.
2. A token with characters that need encoding (`a+b/c=&d`) reaches the API intact. Test in Task 2.
3. A signed-in user opening the link goes straight to the ready state, no login hop, and the address shows `/join`. Test in Task 2.
4. An address typed with spaces or upper case is trimmed before sending; the toast uses the address the API returns (lower case). Test in Task 1.
5. A 401 while joining keeps the saved token, so logging in again brings the user back to "Join a project". Test in Task 2.

---

### Task 1: Share a project by email from the members panel

**Files:**
- Create: `frontend/src/api/shares.ts`, `frontend/src/members/ShareForm.tsx`, `frontend/src/members/ShareForm.test.tsx`, `frontend/e2e/mail.ts`, `frontend/e2e/share.spec.ts`
- Modify: `frontend/src/members/MembersPanel.tsx` (render `<ShareForm project={project} />` after `<InviteForm>` for the owner), `frontend/src/members/MembersPanel.module.css` (`.share`: top border and spacing like `.invite`), `frontend/README.md` (Browser tests: `E2E_MAIL_URL`, `e2e/mail.ts`)

**Interfaces:**
- Produces:
  - `type ShareLink = { email: string; expires_at: string }`
  - `shareProject(projectId: string, email: string): Promise<ShareLink>` → `GET /project/<id>/share?with=<email>` via `apiFetch` and `URLSearchParams`
  - `type JoinResult = { login: string; already_member: boolean; project: Project }`, `joinProject(token: string): Promise<JoinResult>` → `GET /join?token=<token>` (used by Task 2)
  - e2e: `MAIL_URL = process.env.E2E_MAIL_URL ?? "http://127.0.0.1:8025"`; `readJoinLink(request: APIRequestContext, to: string): Promise<string>` polls `GET <MAIL_URL>/api/v1/search?query=to:"<to>"` (up to ~10 s), reads `GET <MAIL_URL>/api/v1/message/<ID>` and returns the first match of `/https?:\/\/\S+\/join\?token=[\w-]+/` in `Text`; `shareViaApi(request, owner: TestUser, projectId: string, email: string): Promise<void>` (expects 200)

- [ ] **Step 1: Write the failing component tests** in `ShareForm.test.tsx` (same setup as `InviteForm.test.tsx`; share key `GET /api/project/<id>/share?with=<encoded>`):
  - `sends a link, clears the field, keeps focus and shows when it expires`: type ` Anna@Example.com `, click "Send link" → request with `with=Anna%40Example.com` (trimmed, case kept); answer `{email: "anna@example.com", expires_at: "2026-11-23T14:05:00Z"}` → toast `Link sent to anna@example.com. It works until ${formatDateTime("2026-11-23T14:05:00Z")}.`; field value `""` and focused; hint "The link works once, for 7 days." is the field's description.
  - `checks the address before sending`: empty → "Enter an email address."; `anna` → "Enter an address like name@example.com."; 255-character address → "Use 254 characters or fewer."; no share request made.
  - `explains each server answer` (table-driven, field keeps the typed address): 422 → "Check the email address and try again."; 429 → "This project already has 10 unused links. Wait until one is used or expires, or invite by login."; 503 `Email sharing is not configured` → "Email isn't set up on this server. Invite people by login instead."; 503 `Email could not be sent` → "Couldn't send the email. Try again later."; 403 → "Only the owner can share the project."; network failure → "Couldn't send the link. Try again."
  - `goes to the projects list when the project is gone`: 404 `Project not found` → URL `/projects`, toast "This project no longer exists."
  - `sends once while a request runs`: two quick submits → one request.
  - `is not shown to a participant`: participant project → no "Send a link by email" field.

- [ ] **Step 2: Run** `npx vitest run src/members/ShareForm.test.tsx` → FAIL (no field "Send a link by email").

- [ ] **Step 3: Implement** `shares.ts` and `ShareForm({ project }: { project: Project })`, modelled on `InviteForm` (same `sending` ref, `isProjectGone` handling, error under the field). Field: label "Send a link by email", `type="email"`, `inputMode="email"`, `autoComplete="off"`, `hint`. Button: `variant="secondary"`, `wide`, text "Send link". Check: trim; empty; `!/^[^\s@]+@[^\s@]+$/.test`; `length > 254`.

- [ ] **Step 4: Run** `npx vitest run src/members` → PASS, and `npm run lint && npm run typecheck`.

- [ ] **Step 5: Write the e2e test** `share.spec.ts` (`test.use({ expectedApiStatuses: [422] })`):
  - `sends a join link by email`: owner signs in, opens own project, fills `share-<uuid8>@example.com` in "Send a link by email", clicks "Send link" → toast starting `Link sent to share-…@example.com`; field empty; `readJoinLink(request, address)` returns a link containing `/join?token=`; `expectAccessible`.
  - `explains an address the server rejects`: `anna@example` → field description "Check the email address and try again.", value kept; `expectAccessible`.

- [ ] **Step 6: Run** against the local stack: `E2E_BASE_URL=http://127.0.0.1:8101 E2E_MAIL_URL=http://127.0.0.1:8035 npx playwright test share.spec.ts` → PASS (desktop and phone).

- [ ] **Step 7: Commit** "Send a project link by email from the members panel".

### Task 2: Join a project from the email link

**Files:**
- Create: `frontend/src/join/joinToken.ts`, `frontend/src/join/JoinLanding.tsx`, `frontend/src/join/JoinPage.tsx`, `frontend/src/join/JoinPage.module.css`, `frontend/src/join/JoinPage.test.tsx`, `frontend/e2e/join.spec.ts`
- Modify: `frontend/src/routes.tsx`, `frontend/src/auth/LoginPage.tsx` + `LoginPage.test.tsx` (join line), `frontend/src/projects/ProjectPage.tsx` (export `RoleBadge`), `frontend/compose.yml` (`api.environment.APP_WEB_URL: ${APP_WEB_URL:-http://127.0.0.1:${WEB_PORT:-8080}}`), `frontend/README.md` (Container: `APP_WEB_URL`; dev server: set `APP_WEB_URL=http://localhost:5173` on the API)

**Interfaces:**
- Consumes: `joinProject`, `JoinResult` (Task 1); `logOut()` from `auth/session`; `useMe()`; `RoleBadge` from `projects/ProjectPage`.
- Produces: `saveJoinToken(token: string): void`, `readJoinToken(): string | null`, `clearJoinToken(): void` (key `project-hub.join-token`); route `/join` = `{ path: "/join", element: <JoinLanding />, children: [{ element: <RequireAuth />, children: [{ index: true, element: <JoinPage /> }] }] }` inside `RouteRoot`.

- [ ] **Step 1: Write the failing component tests** in `JoinPage.test.tsx` (`renderApp`, `mockApi`; join key `GET /api/join?token=<encoded>`):
  - `moves the token out of the address and asks a signed-out user to log in`: `renderApp("/join?token=abc", { token: null })` → heading "Log in", line "Log in or create an account to join the project.", router location `/login?next=%2Fjoin`, `sessionStorage["project-hub.join-token"] === "abc"`.
  - `shows who will join and waits for a click`: signed in, `/join?token=abc` → heading "Join a project", text "You are logged in as @mila. Join with this account, or log out to use another one."; no join request yet; location `/join`.
  - `joins once and shows the project`: click "Join project" twice quickly → one request; answer `{login: "mila", already_member: false, project: {…, my_role: "participant"}}` → heading = project name, "You joined as @mila. You are a participant now.", link "Open project" to `/projects/<id>`; saved token removed.
  - `says when you already have access`: `already_member: true`, `my_role: "owner"` → "You already have access as @mila. The link was not used, so it still works for the person it was sent to."; token removed.
  - `explains a link that doesn't work` for 404 and 422 → heading "This link doesn't work", the spec's text, link "Go to your projects"; token removed.
  - `keeps the link when joining fails`: network failure → alert "Couldn't join the project. Try again.", "Join project" still there, token kept.
  - `keeps the link when the session ends`: 401 → back on log in with `next=%2Fjoin`, token kept.
  - `encodes the token`: token `a+b/c=&d` → request `GET /api/join?token=a%2Bb%2Fc%3D%26d`.
  - `says when there is no link`: `/join` with nothing saved → heading "No invite link", "Open the link from your email again.", link "Go to your projects".
  - `log out keeps the link for the next person`: click "Log out" (mock `POST /api/logout` 204) → log in page, token kept.
  - In `LoginPage.test.tsx`: the join line shows only for `next=/join`.

- [ ] **Step 2: Run** `npx vitest run src/join src/auth/LoginPage.test.tsx` → FAIL.

- [ ] **Step 3: Implement**
  - `JoinLanding`: `useSearchParams`; if `params.has("token")` → `saveJoinToken(params.get("token") ?? "")`, return `<Navigate to="/join" replace />`; else `<Outlet />`.
  - `JoinPage`: `const [token] = useState(readJoinToken)`; `useMutation<JoinResult, Error>` with a `joining` ref guard; `onSuccess`: `clearJoinToken()`, `queryClient.setQueryData(["project", id], project)`, invalidate `["projects"]` and `membersKey(id)`; `onError`: 404/422 → `clearJoinToken()`. Render with `Banner` per spec states; focus the `h1` when the state changes to a result.
  - `LoginPage`: show the join line when `safeNext(next) === "/join"` and no reason text.

- [ ] **Step 4: Run** `npx vitest run` (all) → PASS; `npm run lint && npm run typecheck`.

- [ ] **Step 5: Write the e2e test** `join.spec.ts` (`test.use({ expectedApiStatuses: [404] })`). Helper in the spec: `webJoinUrl(request, link)` requests the mail link with `{ headers: { Accept: "text/html" }, maxRedirects: 0 }`, expects 303 and a `location` that starts with `${baseURL}/join?token=`, returns it.
  - `joins from the email link after logging in`: owner + joiner via `createUser`; project via `createProjectViaApi`; `shareViaApi`; `readJoinLink`; `page.goto(webJoinUrl)` → URL ends `/login?next=%2Fjoin`, join line visible, `expectAccessible`; log in as joiner through the form → "Join a project", "You are logged in as @<joiner>", `page.url()` has no `token`, `expectAccessible`; click "Join project" → heading project name, "You joined as @<joiner>…", `expectAccessible`; click "Open project" → project page shows "Participant" in the banner; then `page.goto(webJoinUrl)` again → "Join project" → "This link doesn't work", `expectAccessible`.
  - `leaves the link for the recipient when the owner opens it`: owner `signIn`, share, `page.goto(webJoinUrl)` → "Join project" → "You already have access as @<owner>…", `expectAccessible`; then another user calls `GET /api/join?token=…` with Bearer → 200 and `already_member: false`.

- [ ] **Step 6: Recreate the stack** so the API gets `APP_WEB_URL` (same `-p f5share` command as at start), then run `E2E_BASE_URL=http://127.0.0.1:8101 E2E_MAIL_URL=http://127.0.0.1:8035 npx playwright test join.spec.ts share.spec.ts` → PASS.

- [ ] **Step 7: Commit** "Join a project from the email link".

### Task 3: Keep join tokens out of the web server's logs

**Files:**
- Modify: `frontend/nginx/default.conf`, `.github/workflows/frontend.yml` (step after "Browser tests"), `frontend/README.md` (Container paragraph)

- [ ] **Step 1: Prove the leak** with the CI check on the stack used in Task 2:
  `docker compose -p f5share -f docker-compose.yml -f frontend/compose.yml logs --no-color web | grep -c 'token='` → a count above 0.

- [ ] **Step 2: Implement** in `default.conf` (http level, before `server`): `map $request_uri $path_only { "~^(?<p>[^?]*)" $p; }`, `map $http_referer $referer_path { "~^(?<r>[^?]*)" $r; default ""; }`, `log_format path_only '$remote_addr - $remote_user [$time_local] "$request_method $path_only $server_protocol" $status $body_bytes_sent "$referer_path" "$http_user_agent"';` and `access_log /var/log/nginx/access.log path_only;` in `server`. Add `location = /api/join` with the same proxy lines as `/api/` plus `error_log /var/log/nginx/error.log crit;` (the comment rule allows one line here: the error log repeats the request line with the token).

- [ ] **Step 3: Check it**: rebuild `web`, run `npx playwright test join.spec.ts`, then the CI command: log has `"GET /api/join HTTP` and `"GET /join HTTP`, and `grep -c 'token='` is 0. Stop `api` (`docker compose … stop api`), `curl 127.0.0.1:8101/api/join?token=probe-123`, check `logs web | grep -c probe-123` is 0, start `api` again.

- [ ] **Step 4: Add the CI step** "Check the web log hides join tokens": fails unless the `web` log contains `"GET /api/join ` and contains no `token=`.

- [ ] **Step 5: Commit** "Keep join tokens out of the web server logs".

### Task 4: Tick F5 in the frontend roadmap

- [ ] Mark F5 ✅ with the PR number in `docs/frontend/roadmap.md` (Epics table and the "Share form, join page" row → done) after the PR is open; commit "Mark frontend F5 share and join as done in the roadmap".
