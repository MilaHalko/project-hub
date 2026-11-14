# F2 — Projects

Date: 2026-11-15
Status: approved by the user (2026-11-15)
Parent design: [`../2026-11-14-frontend-design.md`](../2026-11-14-frontend-design.md)
Roadmap row: [`../roadmap.md`](../roadmap.md) (F2)
Mockup: [`../mockups/f2-projects.html`](../mockups/f2-projects.html) (open in a browser)
API: epic 4, [`docs/superpowers/specs/2026-11-14-projects-access-design.md`](../../superpowers/specs/2026-11-14-projects-access-design.md)

## Intent

After signing in, a user sees their projects and works with them: the list,
creating, editing, the project page and deleting. These are steps 2, 5 and 8 of
the defense demo (see the parent design). The API exists (epic 4, merged); this
epic only calls it.

Sign-in, the token, the API client with the Bearer header, guarded routes and
the 401 "session expired" flow come from F1. F2 reuses them and adds no second
auth layer.

## Goals

- Projects list at `/projects` with tabs All / Owned / Shared with me, "Show
  more" paging, empty, loading and error states.
- Create and edit a project in one dialog.
- Project page at `/projects/<id>` with the holographic header from the style.
- Delete for the owner only, after typing the project name.
- Every screen at 1280 px and 375 px.

## Non-goals

- Documents on the project page and in the list (F4), members panel and invite
  (F3), used space (7a), summary counters (later). No empty placeholders for
  them now.
- Search, sorting options (the API sorts by last update only).
- Anything in the backend.

## Anti-goals

Those of the parent design, and in particular:

- a number the API does not return (documents count, members, space) shown in
  the list or on the page;
- a delete that works without the typed confirmation, or a participant who
  sees "Delete project";
- an action that fails without a visible message;
- a form that loses what the user typed when the request fails.

## Constraints

- API facts (epic 4):
  - `POST /projects` (201), `GET /project/<id>/info`, `PUT /project/<id>/info`
    (200) return `{id, name, description, owner: {id, login}, my_role,
    created_at, updated_at}`; `my_role` is `owner` or `participant`;
  - `GET /projects?role=owner|participant&limit=1..100&offset=0..100000`
    returns a plain list of the same objects plus `documents: []`, newest
    `updated_at` first, no total count;
  - `DELETE /project/<id>`: 204; participant 403 `Only the project owner can
    delete the project`; no access or unknown id 404 `Project not found`;
  - a participant may edit; an id that is not a UUID gives 422;
  - `name` 1–100 characters after trimming, no control characters;
    `description` 0–2000, line breaks allowed;
  - 422 comes as a list of field errors or as one string.
- There is no invite endpoint yet (epic 5). End-to-end tests cannot create a
  participant, so the participant view and the "Shared with me" tab with data
  are proven by component tests now and get an end-to-end test in F3.
- Frontend rules from `CLAUDE.md` and the roadmap: only `frontend/`,
  `docs/frontend/`, the frontend workflow and the roadmap's "Frontend requests"
  section change.

## Approaches

### Create and edit

| Option | Trade-off | Decision |
|---|---|---|
| **One dialog over the current page** | One form component for both; the user stays where they were; the list stays visible behind it | **Chosen** (user, 2026-11-15) |
| Separate pages `/projects/new` and `/projects/<id>/edit` | Deep-linkable, but two more routes and a page for two fields | Rejected |
| Inline form at the top of the list | No dialog, but editing from the project page needs a second form | Rejected |

### Tabs

| Option | Trade-off | Decision |
|---|---|---|
| **Links that set `?role=` in the address** | Survive a reload and the back button; the future "delete account" dialog already links to `/projects?role=owner`; plain links are simple for screen readers (`aria-current`) | **Chosen** (user, 2026-11-15) |
| Tab state in memory with ARIA `tablist` | Lost on reload; arrow-key handling to build | Rejected |

### Paging

| Option | Trade-off | Decision |
|---|---|---|
| **"Show more": pages of 20, ask for 21 to know whether more exist** | Works without a total count | **Chosen** (parent design) |
| Numbered pages | Needs a total the API does not return | Rejected |
| Infinite scroll | Hard to reach the end of the page with a keyboard | Rejected |

### Delete confirmation

| Option | Trade-off | Decision |
|---|---|---|
| **Dialog where the owner types the project name; the button is disabled until it matches** | Strong guard against a wrong click; one extra step in the demo | **Chosen** (user, 2026-11-15, against the planner's recommendation) |
| Dialog with "Cancel" / "Delete project" only | Faster, weaker guard | Rejected |

## Additions beyond the roadmap row

Proposed on 2026-11-15; the user's decisions:

| Addition | Decision | Reason |
|---|---|---|
| Character counter under the description (`57 / 2000`) | **Accepted** | The limit is visible before an error |
| "Discard changes?" when closing the dialog with unsaved edits | **Rejected** | Two short fields; not worth the extra dialog |
| Type the project name to confirm a delete | **Accepted** | One click must never delete a project |
| Own empty state for "Shared with me" without a create button | **Accepted** | A user cannot create a project shared with them |

## Design

### Routes

| Path | Screen |
|---|---|
| `/` | redirects to `/projects` |
| `/projects` | list, tab All |
| `/projects?role=owner` | list, tab Owned |
| `/projects?role=participant` | list, tab Shared with me |
| `/projects/<id>` | project page |

An unknown `role` value shows the All tab. All routes are guarded by F1.

### Projects list (mockup 1, 2, 8)

- Banner: tag `HI, <LOGIN>` as in F1 (`PROJECT_HUB` while the user is loading or
  if `/users/me` fails; kept by the user on 2026-11-15), title "Your projects",
  line "Projects you own and projects you were invited to."
- Toolbar: tab links All / Owned / Shared with me (current one marked with
  `aria-current="page"`), primary button "New project" with a plus icon.
- Table columns: Project (name as the link to the project page, description on
  one line, cut with an ellipsis; "No description" in muted italics when empty),
  Role (Owner badge violet, Participant badge mint), Owner (`login`, with
  " (you)" when `my_role` is `owner`), Updated (relative time, the exact date
  and time in a `<time datetime>` with a `title`).
- Paging: the first request asks `limit=21, offset=0`; 20 rows are shown, a
  21st means "Show more" appears. Each click asks the next `21` from `offset`
  = rows shown, and appends. While a page loads, the button shows a spinner and
  ignores clicks. Each tab pages on its own.
- States:
  - first load: three skeleton rows;
  - error: "Couldn't load your projects." with "Try again", which repeats the
    request; an error while loading more keeps the shown rows and shows the
    same message under them;
  - empty, tabs All and Owned: "Create your first project" / "A project keeps
    your documents and the people you work with in one place." and the
    "New project" button; the toolbar button is hidden then, so there is one
    primary button;
  - empty, tab Shared with me: "Nothing shared with you yet" / "When someone
    invites you to a project, it shows up here.", no button.
- Phone (below 768 px): the table becomes a list of cards (name and badge,
  description, "alex (you), updated 2 hours ago"); tabs take the full width
  with the full labels and at least 40 px height; "New project" and
  "Show more" are full width.

Relative time (builder may adjust): under a minute "just now"; minutes and
hours "5 minutes ago", "2 hours ago"; the day before "yesterday"; older in the
current year "Nov 12"; other years "Nov 12, 2025". English locale, built-in
`Intl`, no date library.

### Project dialog (mockup 3)

- Opened by "New project" (title "New project", submit "Create project") and by
  "Edit" on the project page (title "Edit project", fields filled, submit
  "Save changes").
- Fields: Name (required), Description (optional, textarea, counter
  `n / 2000` under it).
- Checks before sending, shown next to the field on submit and then while
  typing: empty or blank name "Enter a project name."; name over 100
  characters after trimming "Use 100 characters or fewer."; a tab, line break
  or other control character in the name "Remove tabs and line breaks from the
  name."; description over 2000 "Use 2000 characters or fewer." Nothing is sent
  while a check fails. The name is sent trimmed.
- API errors: 422 field list → next to its field; 422 string → above the
  buttons; network or 500 → "Couldn't create the project. Try again." (edit:
  "Couldn't save the changes. Try again."); 404 on edit → toast "This project
  no longer exists." and go to `/projects`. The dialog keeps what was typed.
- Success: create → open `/projects/<new id>`, toast "Project created"; edit →
  close, the page shows the new values, toast "Changes saved". Lists and the
  project are refreshed from the API.
- The dialog is modal: focus goes to the name field, stays inside the dialog,
  Esc and "Cancel" close it, focus returns to the button that opened it. On a
  phone it rises from the bottom with full-width buttons.

### Project page (mockup 4, 5, 7)

- Breadcrumb "Projects / <name>", "Projects" links back to the list.
- Banner: role badge on a white background, the name in Space Mono, the
  description with its line breaks kept (no raw HTML), and the actions: "Edit"
  for everyone, "Delete project" (destructive secondary) only when `my_role`
  is `owner`.
- Under the banner a details row: Owner (`login`, " (you)" for the owner),
  Created (date), Updated (relative, exact in `title`). Stacked on a phone.
- The browser tab title is "<name> — Project Hub".
- States: loading (skeleton banner); 404, or 422 for an id that is not a UUID →
  "Project not found" / "It may have been deleted, or you don't have access to
  it." with "Back to projects"; other errors → "Couldn't load the project." with
  "Try again".

### Delete (mockup 6)

- "Delete project" opens an alert dialog: title "Delete this project?", text
  "This deletes **<name>** with all its documents and removes everyone's
  access. You can't undo this.", field "Type the project name to confirm",
  buttons "Cancel" and "Delete project" (danger).
- The button is enabled only when the typed text, trimmed, equals the project
  name exactly (case matters). Pasting is allowed.
- Success (204): go to `/projects`, toast "Project deleted", the project is gone
  from every tab.
- Errors: 403 → "You don't have permission to do this." in the dialog; 404 →
  toast "This project no longer exists." and go to `/projects`; network or 500
  → "Couldn't delete the project. Try again." in the dialog.

### Words

All copy is in the mockup and above. It follows `style.md`: sentence case, verbs
on buttons, no "please", no "successfully", no exclamation marks. The same
action keeps its name: "New project" → "Create project" → "Project created";
"Delete project" → "Project deleted".

## Acceptance criteria

Behaviour is proven by component tests (Vitest, API mocked) and end-to-end tests
(Playwright against the real stack, each test creating its own user through
`POST /auth`, axe WCAG 2.1 AA on every page and open dialog).

| # | Given / when / then | Proven by |
|---|---|---|
| 1 | Given a signed-in user with projects, when they open `/projects`, then they see them newest update first, each with the name as a link, description, role badge, owner and updated time | component, e2e |
| 2 | Given the list, when the user picks Owned or Shared with me, then only projects with that role show, the address has `?role=owner` or `?role=participant`, and a reload keeps the tab; `/` opens `/projects` | component, e2e (Owned) |
| 3 | Given 21 or more projects, when the list opens, then 20 show with "Show more", and a click appends the next ones; with 20 or fewer there is no button | component, e2e |
| 4 | Given no projects, then All and Owned show "Create your first project" with "New project", and Shared with me shows "Nothing shared with you yet" without a button | component |
| 5 | Given the list request is slow or fails, then skeleton rows show, and on failure "Couldn't load your projects." with "Try again" that repeats the request | component |
| 6 | Given the list, when the user creates a project with a name and description, then its page opens with that name, the toast "Project created" shows, and the list has it first | component, e2e |
| 7 | Given the dialog, when the name is empty, too long or has a tab or line break, or the description is over 2000, then the field shows its message and nothing is sent; the counter shows `n / 2000` | component |
| 8 | Given the API answers 422 (field list or string) or the network fails, then the message shows next to the field or above the buttons and the typed values stay | component |
| 9 | Given the owner opens a project, then the banner shows the Owner badge, name, description with line breaks, "Edit" and "Delete project", and the details show Owner "login (you)", Created and Updated | component, e2e |
| 10 | Given a participant opens a project, then the banner shows the Participant badge and "Edit" without "Delete project" | component (e2e in F3, when invites exist) |
| 11 | Given a project id that does not exist, is not a UUID or belongs to someone else, then "Project not found" shows with "Back to projects" | component, e2e (another user's project) |
| 12 | Given the project page, when the user edits name and description and saves, then the banner shows the new values and the toast "Changes saved" | component, e2e |
| 13 | Given the owner clicks "Delete project", then "Delete project" in the dialog stays disabled until the exact name is typed; after confirming, the list opens with the toast "Project deleted" and the project is gone | component, e2e |
| 14 | Given a delete answered with 403, 404 or a network error, then the matching message from "Delete" above shows | component |
| 15 | Dialogs: focus moves in, stays in, Esc and Cancel close, focus returns to the opener | component, e2e (keyboard) |
| 16 | Every page and open dialog visited in e2e has no WCAG 2.1 AA violation | e2e axe |
| 17 | At 375 px the list shows cards and no page scrolls sideways | e2e at 375 px, screenshots |
| 18 | Lint, type check, component tests, production build and `npm audit --audit-level=high` pass; CI jobs `frontend` and `e2e` are green | commands, CI |
| 19 | No backend file changes: `git diff --stat origin/main...` lists only allowed paths | command |

## Left to the builder

- Component, hook and file names inside `frontend/src/projects/` and `ui/`.
- How the modal dialog is built (native `<dialog>` with `showModal()` or a
  small focus-trap component), as long as criterion 15 holds and component
  tests can run it.
- The plus icon and spinner from the icon set F0 installed (`lucide-react`).
- Query keys and how lists are refreshed after create, edit and delete.
- Whether API types are written by hand or generated (parent design).

## Carried to later epics

- F3: e2e for the participant view and the Shared with me tab with data, once
  invites exist; members panel under the banner.
- F4: documents section under the banner and a documents column in the list
  when the API fills `documents`.
- 7a: used space in the list and on the page.
