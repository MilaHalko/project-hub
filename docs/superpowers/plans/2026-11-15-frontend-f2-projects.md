# Frontend F2 — Projects: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Projects list with tabs and paging, create and edit in one dialog, project page, delete with a typed confirmation.

**Architecture:** One API module `src/api/projects.ts` on top of F1's `apiFetch`; TanStack Query for the list (`useInfiniteQuery`, one query per tab) and the project (`useQuery`); mutations invalidate `["projects"]` and update `["project", id]`. Dialogs use the native `<dialog>` element with `showModal()` (focus trap, Esc and the inert background come from the browser). Routes `/projects`, `/projects/:projectId`, `/` redirects to `/projects`; F1's `RequireAuth` guards them.

**Tech Stack:** React 19, React Router 8, TanStack Query 5, TypeScript strict, CSS Modules, Vitest + Testing Library, Playwright + `@axe-core/playwright`.

**Spec:** [`docs/frontend/specs/2026-11-15-f2-projects-design.md`](../../frontend/specs/2026-11-15-f2-projects-design.md) and the mockup [`docs/frontend/mockups/f2-projects.html`](../../frontend/mockups/f2-projects.html). All UI copy is copied from the spec, word for word.

## Global Constraints

- Change only `frontend/`, `docs/frontend/`, `docs/superpowers/plans/`. Never `src/`, `tests/`, migrations, `pyproject.toml`, `poetry.lock`, root `Dockerfile`, `docker-compose.yml`, `ci.yml`.
- Reuse F1: `apiFetch` (`src/api/client.ts`), `ApiError`, `fieldErrors`, `messageFor` (`src/api/errors.ts`), `RequireAuth`, `useMe`, `Button` (`busy`, `variant`), `Field`, `Banner`, `useToast`, `mockApi`, `renderApp`, e2e `createUser`/`apiToken`/`signIn`, `expectAccessible`, `expectedApiStatuses`. No second auth layer, no new runtime dependency.
- No `dangerouslySetInnerHTML`/`innerHTML`; API text is rendered as React text.
- No comments or docstrings unless the code looks safe to change but is not (`CLAUDE.md` "Comments"); check each diff for new `//`, `/*`, `{/*` lines before committing.
- One commit per task, plain-words imperative subject ≤ 70 chars, 1–3 line body, **no `Co-Authored-By` trailer**.
- Tests prove behaviour: what the user sees (roles, labels, text) and which requests go out; no snapshots; no tests of `src/test/` helpers.
- Every page or open dialog visited in a new e2e test runs `expectAccessible(page)` in the state under test. E2e tests run in both Playwright projects `desktop` (1280) and `phone` (375).
- Each e2e test creates its own user (`signIn(page, request)`) and its data through the API; no test depends on another.
- Checks per task in `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, and the task's e2e spec against the stack.

## Running e2e locally

```bash
# repository root; project name and ports keep it apart from other sessions
APP_DB_PORT=55442 APP_PORT=8012 WEB_PORT=8092 APP_JWT_SECRET=$(openssl rand -hex 32) \
  docker compose -p f2projects -f docker-compose.yml -f frontend/compose.yml up -d --build --wait
# frontend/
E2E_BASE_URL=http://127.0.0.1:8092 npx playwright test e2e/<spec>.spec.ts
```

Re-run the compose command (it rebuilds `web`) after changing `frontend/src`.

## Shared interfaces

```ts
// src/api/projects.ts (Task 1 creates it with listProjects; later tasks add their function)
export type ProjectRole = "owner" | "participant";
export type Project = {
  id: string; name: string; description: string;
  owner: { id: string; login: string };
  my_role: ProjectRole; created_at: string; updated_at: string;
};
export type ProjectInput = { name: string; description: string };
export function listProjects(q: { role?: ProjectRole; limit: number; offset: number }): Promise<Project[]>;
//   GET /projects?role=<role>&limit=<n>&offset=<n>  (URLSearchParams in this order; no role key for All)
export function getProject(id: string): Promise<Project>;               // GET /project/<id>/info      (Task 3)
export function createProject(body: ProjectInput): Promise<Project>;    // POST /projects              (Task 4)
export function updateProject(id: string, body: ProjectInput): Promise<Project>; // PUT /project/<id>/info (Task 5)
export function deleteProject(id: string): Promise<void>;               // DELETE /project/<id>        (Task 6)
// ids go through encodeURIComponent

// src/projects/time.ts (Task 1)
export function formatUpdated(iso: string, now?: Date): string; // "just now" | "5 minutes ago" | "1 hour ago" | "yesterday" | "Nov 12" | "Nov 12, 2025"
export function formatDate(iso: string): string;                // "Nov 12, 2026"
// projects/ownerLabel.ts or inside time.ts is the builder's call:
export function ownerLabel(p: Project): string;                 // "alex (you)" when my_role === "owner", else "alex"

// Query keys
["projects", role ?? "all"]   // infinite list per tab
["project", id]               // one project
```

## Review Focus

1. A project name or description that looks like HTML (`<img src=x onerror=alert(1)>`) → shown as plain text everywhere (Task 3 test).
2. A 100-character name without spaces → wraps in the list, the banner and the dialog; nothing scrolls sideways at 375 px (Task 1 and Task 3 e2e check `scrollWidth <= innerWidth`).
3. A double click on "Create project" / "Save changes" / "Delete project" → one request (Tasks 4, 5, 6 tests, via `Button busy`).
4. Typed confirmation with extra spaces → accepted; different case → button stays disabled (Task 6 test).
5. Switching tabs after "Show more" → the other tab starts at its own first page; going back keeps the loaded pages (Task 2 test).

---

### Task 1: See your projects at /projects with tabs and empty states

**Files:**
- Create: `src/api/projects.ts`, `src/projects/time.ts`, `src/projects/ProjectsTable.tsx` + `.module.css`, `e2e/projects.ts`, `e2e/projects.spec.ts`
- Modify: `src/projects/ProjectsPage.tsx` + `.module.css`, `src/routes.tsx` (`/projects`, `/` → `<Navigate to="/projects" replace />`), `src/ui/Layout.tsx` (nav "Projects" → `/projects`, active on `/projects/...` too), `src/ui/NotFoundPage.tsx` ("Go to projects" → `/projects`), `src/test/mockApi.ts` (default answer `GET /api/projects?limit=21&offset=0` → `200 []`, like the default `users/me`), `e2e/shell.spec.ts` (expect `/projects` after "Go to projects")
- Test: `src/projects/ProjectsPage.test.tsx` (rewrite), `src/projects/time.test.ts`, `src/ui/NotFoundPage.test.tsx` (href `/projects`)

**Interfaces:** Produces `Project`, `ProjectRole`, `listProjects`, `formatUpdated`, `formatDate`, `ownerLabel`, `e2e/projects.ts`:

```ts
export async function createProjectViaApi(
  request: APIRequestContext, user: TestUser,
  body: { name: string; description?: string },
): Promise<{ id: string; name: string }>; // POST /api/projects with apiToken(user); throws unless 201
```

- [ ] **Step 1: Write the failing tests**
  - `time.test.ts` with `now = new Date("2026-11-15T12:00:00")` (local time): 30 s before → "just now"; 1 min → "1 minute ago"; 5 min → "5 minutes ago"; 1 h → "1 hour ago"; 2 h → "2 hours ago"; `2026-11-14T09:00` → "yesterday"; `2026-11-12T10:00` → "Nov 12"; `2025-11-12T10:00` → "Nov 12, 2025"; a time in the future → "just now". `formatDate("2026-11-12T10:00:00Z")` → "Nov 12, 2026".
  - `ProjectsPage.test.tsx` (keep F1's greeting tests: "HI, MILA", PROJECT_HUB while loading and on `/users/me` 500):
    - `renderApp("/")` lands on the "Your projects" heading and requests `GET /api/projects?limit=21&offset=0`;
    - two projects (one owner, one participant) → each row has the name as a link to `/projects/<id>`, its description, badge "Owner"/"Participant", owner "mila (you)"/"sam", and an updated text; empty description shows "No description";
    - tab links "All", "Owned", "Shared with me": the current one has `aria-current="page"`; clicking "Owned" requests `GET /api/projects?role=owner&limit=21&offset=0` and only its rows show; `renderApp("/projects?role=participant")` starts on "Shared with me"; `?role=bogus` shows All;
    - `[]` on All → heading "Create your first project", text "A project keeps your documents and the people you work with in one place.", one "New project" button (the toolbar button is not shown); same on Owned; on Shared with me → "Nothing shared with you yet", "When someone invites you to a project, it shows up here.", no "New project" button in the empty state (the toolbar one stays);
    - a pending request → three skeleton rows (`aria-busy="true"` on the list region is enough to assert); a 500 → "Couldn't load your projects." and "Try again", which sends the request again and shows the rows.
  - The "New project" buttons exist but do nothing until Task 4.
- [ ] **Step 2: Run `npm test -- src/projects` and see them fail** for missing rows/tabs, not for a mock error.
- [ ] **Step 3: Implement** `listProjects`, `time.ts`, `ownerLabel`, the page (banner as in F1 with `HI, <LOGIN>` tag, line "Projects you own and projects you were invited to."), tab links (`<nav aria-label="Filter projects">` with `Link`s and `aria-current`), `ProjectsTable` as one markup: a table at ≥ 768 px that CSS turns into cards below 768 px (no second copy of the rows in the DOM). Updated cell: `<time dateTime={iso} title={exact local date and time}>{formatUpdated(iso)}</time>`. Use `useInfiniteQuery` already (page size 20, request 21) so Task 2 only adds the button.
- [ ] **Step 4: Run `npm run lint && npm run typecheck && npm test`** — all pass, including F1's suites.
- [ ] **Step 5: E2e `projects.spec.ts`**: a user with two projects made through the API sees both on `/projects`, newest first; "Owned" shows them and the URL is `/projects?role=owner`, a reload keeps the tab; "Shared with me" shows "Nothing shared with you yet"; a fresh user sees "Create your first project". Create one project with a 100-character name without spaces and assert `document.documentElement.scrollWidth <= window.innerWidth`. `expectAccessible` in each state. Update `shell.spec.ts` (`/projects`). Run the whole e2e suite: all pass.
- [ ] **Step 6: Commit** `See your projects at /projects with tabs and empty states`.

### Task 2: Load more projects with "Show more"

**Files:**
- Modify: `src/projects/ProjectsPage.tsx`, `src/projects/ProjectsTable.tsx` (+ css)
- Test: `src/projects/ProjectsPage.test.tsx`, `e2e/projects.spec.ts`

- [ ] **Step 1: Failing tests**
  - 21 projects on the first page → 20 rows and a "Show more" button; click → `GET /api/projects?limit=21&offset=20`, 5 more → 25 rows, no button; exactly 20 → no button;
  - while the next page loads the button is busy (`aria-busy="true"`) and a second click sends no second request;
  - the next page fails → the 20 rows stay, "Couldn't load your projects." with "Try again" under them, which repeats `offset=20`;
  - Review Focus 5: load page 2 on All, switch to Owned → first-page request for owner and 0 extra rows; back to All → 40 rows without a new request for `offset=0` (cached).
- [ ] **Step 2: See them fail.**
- [ ] **Step 3: Implement** with `fetchNextPage` / `hasNextPage` (`getNextPageParam`: `lastPage.length > 20 ? offset + 20 : undefined`; show the first 20 of each page). Focus stays on the button after loading; the button is full width below 768 px.
- [ ] **Step 4: lint, typecheck, test pass.**
- [ ] **Step 5: E2e**: a user with 21 projects (created through the API in a loop) sees 20, clicks "Show more", sees 21 and no button. `expectAccessible`. Pass.
- [ ] **Step 6: Commit** `Load more projects with Show more`.

### Task 3: Open a project page with its header and details

**Files:**
- Create: `src/projects/ProjectPage.tsx` + `.module.css`, `e2e/project-page.spec.ts`
- Modify: `src/api/projects.ts` (`getProject`), `src/routes.tsx` (`projects/:projectId`)
- Test: `src/projects/ProjectPage.test.tsx`

- [ ] **Step 1: Failing tests**
  - owner project → breadcrumb link "Projects" (to `/projects`) and the name; `h1` with the name; badge "Owner"; description with its line break kept (`"Line one\nLine two"` — assert the element's `textContent` and that the CSS class sets `white-space: pre-line`, or render lines; builder's call); buttons "Edit" and "Delete project"; details "Owner" → "mila (you)", "Created" → "Nov 12, 2026", "Updated" → a relative text; `document.title` is "<name> — Project Hub";
  - participant project → badge "Participant", "Edit", no "Delete project", owner "sam";
  - Review Focus 1: name `<img src=x onerror=alert(1)>` → appears as text in the heading, no `img` element in the document;
  - 404 → heading "Project not found", text "It may have been deleted, or you don't have access to it.", link "Back to projects" to `/projects`; 422 (id `abc`) → the same;
  - 500 → "Couldn't load the project." with "Try again" that repeats the request; pending → a skeleton banner (`aria-busy="true"`).
  - "Edit" and "Delete project" do nothing until Tasks 5 and 6.
- [ ] **Step 2: See them fail.**
- [ ] **Step 3: Implement** the page. Banner: reuse `Banner` if it can take the badge and the actions (`aside`/children), otherwise a project header in this folder with the same tokens; the `h1` must stay the first heading so F1's `useFocusHeadingOnNavigate` focuses it. The not-found state follows F1's `NotFoundPage` pattern (Banner, tag `ERROR 404`), with this page's texts. Details as a `<dl>`, three columns, stacked below 768 px.
- [ ] **Step 4: lint, typecheck, test pass.**
- [ ] **Step 5: E2e** (`expectedApiStatuses: [404]` only in the not-found test): open a project made through the API from the list by clicking its name → the page shows name, "Owner" badge, "Edit", "Delete project", owner "<login> (you)"; a 100-character name wraps without sideways scroll; a second user opening the first user's project URL sees "Project not found" and "Back to projects" leads to `/projects`. `expectAccessible` on each page. Pass.
- [ ] **Step 6: Commit** `Open a project page with its header and details`.

### Task 4: Create a project from the list and land on its page

**Files:**
- Create: `src/ui/Dialog.tsx` + `.module.css`, `src/ui/TextAreaField.tsx` (same look as `Field`, reuses `Field.module.css`), `src/projects/ProjectDialog.tsx` + `.module.css`, `src/projects/projectRules.ts`, `e2e/create-project.spec.ts`
- Modify: `src/api/projects.ts` (`createProject`), `src/projects/ProjectsPage.tsx` (both "New project" buttons open the dialog), `src/test/setup.ts` (jsdom has no `showModal`: stub `HTMLDialogElement.prototype.showModal`/`close` to set/remove `open` and fire `close`)
- Test: `src/projects/projectRules.test.ts`, `src/projects/ProjectDialog.test.tsx`, `src/projects/ProjectsPage.test.tsx`

**Interfaces:**

```ts
// src/ui/Dialog.tsx
export function Dialog(props: {
  open: boolean; title: string; onClose: () => void;
  role?: "dialog" | "alertdialog"; children: ReactNode;
}): JSX.Element; // <dialog aria-labelledby=title id>; showModal() when open turns true, close() when false;
                 // the native "cancel" (Esc) calls onClose; focus returns to the opener (browser does it on close)

// src/projects/projectRules.ts
export type ProjectErrors = { name?: string; description?: string };
export function checkProject(input: ProjectInput): ProjectErrors;
// name.trim() === "" → "Enter a project name."; name.trim().length > 100 → "Use 100 characters or fewer.";
// /\p{Cc}/u in name → "Remove tabs and line breaks from the name."; description.length > 2000 → "Use 2000 characters or fewer."

// src/projects/ProjectDialog.tsx
export function ProjectDialog(props: {
  open: boolean; onClose: () => void;
  project?: Project;            // edit mode when given (Task 5)
}): JSX.Element;
```

- [ ] **Step 1: Failing tests**
  - `projectRules.test.ts`: each message above; 100 characters plus surrounding spaces is fine; `"a\tb"` gives the control-character message; a 2000-character description is fine, 2001 is not.
  - `ProjectDialog.test.tsx` (create mode, rendered inside the app via `renderApp("/projects")` and a click on "New project"): dialog "New project" with "Name" focused, "Description (optional)", counter "0 / 2000" that follows typing; "Create project" with an empty name shows "Enter a project name." next to Name and sends nothing; valid input sends `POST /api/projects` with `{"name":"Website redesign","description":"..."}` (name trimmed), then the URL is `/projects/<new id>`, the toast "Project created" shows; a double click sends one request; 422 field list (`loc: ["body","name"]`) → message next to Name; 422 string → message above the buttons; network error → "Couldn't create the project. Try again." and the typed values stay; "Cancel" closes the dialog and sends nothing.
  - `ProjectsPage.test.tsx`: the empty-state "New project" opens the same dialog.
- [ ] **Step 2: See them fail.**
- [ ] **Step 3: Implement.** Checks run on submit, then on every change after the first submit. On success invalidate `["projects"]`, `setQueryData(["project", id], created)`, navigate, toast. Below 768 px the dialog sits at the bottom, full width, buttons stacked full width ("Cancel" under the primary). The page behind is inert (native modal).
- [ ] **Step 4: lint, typecheck, test pass.**
- [ ] **Step 5: E2e**: a fresh user clicks "New project" in the empty state, `expectAccessible` with the dialog open, presses Esc → the dialog is gone and the "New project" button is focused; opens it again, submits empty → "Enter a project name."; fills name and description, "Create project" → the project page with the name as `h1`, toast "Project created"; back to "Projects" → the project is first. Pass.
- [ ] **Step 6: Commit** `Create a project from the list and land on its page`.

### Task 5: Edit a project's name and description

**Files:**
- Modify: `src/api/projects.ts` (`updateProject`), `src/projects/ProjectDialog.tsx`, `src/projects/ProjectPage.tsx`
- Create: `e2e/edit-project.spec.ts`
- Test: `src/projects/ProjectDialog.test.tsx`, `src/projects/ProjectPage.test.tsx`

- [ ] **Step 1: Failing tests**: "Edit" on the page opens "Edit project" with both fields filled and the counter at the description's length; "Save changes" sends `PUT /api/project/<id>/info` with the trimmed name and the description; on 200 the dialog closes, the banner shows the new name and description, toast "Changes saved"; a participant can edit too; network error → "Couldn't save the changes. Try again." and values stay; 404 → toast "This project no longer exists." and the URL is `/projects`; a double click sends one request; reopening after "Cancel" shows the saved values, not the abandoned edits.
- [ ] **Step 2: See them fail.**
- [ ] **Step 3: Implement**: on success `setQueryData(["project", id], updated)` and invalidate `["projects"]`; on 404 `removeQueries(["project", id])`, invalidate `["projects"]`, navigate, error toast.
- [ ] **Step 4: lint, typecheck, test pass.**
- [ ] **Step 5: E2e**: open a project made through the API, "Edit", `expectAccessible` with the dialog open, change both fields, "Save changes" → new name in the `h1`, toast "Changes saved"; the list shows the new name first. Pass.
- [ ] **Step 6: Commit** `Edit a project's name and description`.

### Task 6: Delete a project after typing its name

**Files:**
- Create: `src/projects/DeleteProjectDialog.tsx` + `.module.css`, `e2e/delete-project.spec.ts`
- Modify: `src/api/projects.ts` (`deleteProject`), `src/projects/ProjectPage.tsx`
- Test: `src/projects/DeleteProjectDialog.test.tsx` (through `renderApp`)

- [ ] **Step 1: Failing tests**: "Delete project" opens an `alertdialog` "Delete this project?" with "This deletes <name> with all its documents and removes everyone's access. You can't undo this." (name in bold), field "Type the project name to confirm", "Cancel", and a danger "Delete project" that is disabled; typing part of the name keeps it disabled; the name in other case keeps it disabled; the name with spaces around enables it; click sends `DELETE /api/project/<id>` once (double click), then the URL is `/projects` and the toast "Project deleted" shows; 403 → "You don't have permission to do this." in the dialog; 404 → toast "This project no longer exists." and `/projects`; network → "Couldn't delete the project. Try again." in the dialog; "Cancel" closes and clears the field.
- [ ] **Step 2: See them fail.**
- [ ] **Step 3: Implement**: the confirm button uses `Button variant` for a filled danger button (add `"danger-solid"` or similar to `Button` only if no existing variant fits; the style is `--color-danger` background, white text). On success `removeQueries(["project", id])`, invalidate `["projects"]`, navigate, toast.
- [ ] **Step 4: lint, typecheck, test pass.**
- [ ] **Step 5: E2e**: open a project made through the API, "Delete project", `expectAccessible` with the dialog open, the button is disabled, type the name, confirm → `/projects`, toast "Project deleted", the project is not in the list; opening its old URL shows "Project not found" (`expectedApiStatuses: [404]`). Pass.
- [ ] **Step 6: Commit** `Delete a project after typing its name`.

### Task 7: Document F2 for the next epics

**Files:**
- Modify: `frontend/README.md` (e2e helper `createProjectViaApi`, the `f2projects` local stack line, default `GET /api/projects` answer in `mockApi`, `Dialog` and the jsdom `showModal` stub), `docs/frontend/specs/2026-11-15-f2-projects-design.md` (only if a builder's call changed something: write it under "Left to the builder")

- [ ] **Step 1:** Write the README paragraph in the style of F1's "For the next epics" paragraph.
- [ ] **Step 2:** `npm run lint` (Prettier checks Markdown) passes.
- [ ] **Step 3: Commit** `Note the projects helpers for the next frontend epics`.
