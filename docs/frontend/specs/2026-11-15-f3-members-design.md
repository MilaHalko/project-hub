# F3 — Members and invites

Date: 2026-11-15
Status: approved by the user (2026-11-15)
Parent design: [`../2026-11-14-frontend-design.md`](../2026-11-14-frontend-design.md)
Roadmap row: [`../roadmap.md`](../roadmap.md) (F3)
Mockup: [`../mockups/f3-members.html`](../mockups/f3-members.html) (open in a browser)
API: epic 4 (members list) and epic 5 (invite, remove, leave),
[`docs/superpowers/specs/2026-11-15-invites-design.md`](../../superpowers/specs/2026-11-15-invites-design.md)

## Intent

The project page shows who works on the project, and the owner adds people to it
by their login. These are steps 4 and 5 of the defense demo: the owner invites a
second user, that user logs in and sees the project without "Delete project".
The API exists (epics 4 and 5, merged); this epic only calls it.

## Goals

- A members panel on the project page: avatar, login, role badge, owner first.
- An invite form in the panel, for the owner only.
- Remove a participant (owner) and leave a project (participant), each after a
  confirmation (extras accepted by the user, 2026-11-15).
- The end-to-end test for the participant view carried over from F2.
- Every state at 1280 px and 375 px.

## Non-goals

- Display names and picked avatars (F1b; they need a backend task first).
- Share by email and the join page (F5, after backend epic 10).
- Documents (F4), used space (7a).
- Transferring ownership, more roles than owner and participant.
- Anything in the backend.

## Anti-goals

Those of the parent design and F2, and in particular:

- a participant who sees the invite form or a "Remove" button;
- an owner who sees "Leave project" (the API answers 409 for it);
- a remove or leave that happens on one click, without the confirmation;
- an invite that fails without a message next to the field, or clears what
  was typed when it fails;
- a toast that says "Invite sent": nothing is sent, the user is added at once.

## Constraints

- API facts (epics 4 and 5):
  - `GET /project/<id>/members` → `[{id, login, role, joined_at}]`, owner
    first, then participants by `joined_at`; any member may read it; no access
    or unknown id → 404 `Project not found`;
  - `POST /project/<id>/invite?user=<login>` (no body) → 201 with one member
    in the same shape, `role: "participant"`. Errors in this order: 422 (login
    empty or over 32 characters; id not a UUID), 404 `Project not found`, 403
    `Only the project owner can invite users`, 404 `User not found` (exact,
    case-sensitive login), 409 `You already own this project`, 409 `User is
    already a participant of this project`;
  - `DELETE /project/<id>/members/<user_id>` → 204. The owner removes a
    participant; a participant may remove only their own id, which means
    leaving. Errors in this order: 404 `Project not found`, 403 `Only the
    project owner can remove participants`, 409 `The owner cannot leave the
    project`, 404 `Participant not found`;
  - neither call changes the project's `updated_at`;
  - logins are 3–32 characters of `A–Z a–z 0–9 _ . -` (registration rule).
- The two 404s of one call differ only by `detail`; the UI tells them apart by
  that text.
- The user's own id comes from `GET /users/me` (`useMe`, already loaded by the
  layout).
- Frontend rules from `CLAUDE.md` and the roadmap: only `frontend/`,
  `docs/frontend/`, the frontend workflow and the roadmap's "Frontend requests"
  section change.

## Approaches

### Where the invite form lives

| Option | Trade-off | Decision |
|---|---|---|
| **Field and button at the bottom of the members panel** | One step, nothing opens over the page, the new member appears right above the field; matches the approved `look.html` | **Chosen** (user, 2026-11-15) |
| "Invite people" button opening a dialog | Smaller panel, but one more click and the dialog hides the list it changes | Rejected |
| Own page `/projects/<id>/members` | A route and a page for one field; more navigation in the demo | Rejected |

### Confirming remove and leave

| Option | Trade-off | Decision |
|---|---|---|
| **Alert dialog with Cancel and the action** (as F2's delete, without typing the name) | One extra click; consistent with F2 | **Chosen** (planner's call, shown to the user 2026-11-15) |
| Act at once, "Undo" in the toast | Faster, but undo would mean inviting again, and a participant who left cannot invite themselves back | Rejected |
| Type the login or project name to confirm | Strong guard for something that is easy to reverse (invite again) | Rejected |

## Additions beyond the roadmap row

Proposed on 2026-11-15; the user's decisions:

| Addition | Decision | Reason |
|---|---|---|
| Remove a participant (owner) | **Accepted** | A wrong invite can be undone in the UI |
| Leave a project (participant) | **Accepted** | Shows in the demo that the server lets a participant remove only themselves |
| Toast "<login> added to the project" instead of the parent design's "Invite sent" | **Planner's call** | Nothing is sent; the user is a member at once |

## Design

### Project page layout (mockup 1, 2, 6)

- Under the banner the page has two columns: on the left the details row from
  F2 (Owner, Created, Updated), on the right the members panel, about 280 px
  wide. F4 adds the documents to the left column under the details; there is
  no empty placeholder for them now.
- Below 768 px one column: details, then members.
- Banner actions: owner "Edit" and "Delete project" (as F2); participant
  "Edit" and "Leave project" (destructive secondary).

### Members panel (mockup 1, 2, 3)

- A bordered panel with the heading "Members" (`h2`) and the count next to it
  in muted text ("Members 3"); the count is the length of the list.
- One row per member in API order: avatar (28 px, F1's default from the user
  id), login, " (you)" after the signed-in user's own login, and the role badge
  under the login (Owner violet, Participant mint, as in the list).
- For the owner, each participant row has a small secondary "Remove" button
  with the accessible name "Remove <login>". The owner's own row has none.
- Badges sit under the login, so they line up whether or not a row has
  "Remove", and the login gets the whole width between the avatar and
  "Remove": a short login stays on one line, a 32-character one takes at most
  two. (Changed while building, 2026-11-15: with the badge beside the login, as
  in the mockup, real logins such as `sam5343` broke into two lines and a
  32-character one into five in the 280 px panel.)
- On a phone "Remove" is at least 32 px tall.
- States:
  - loading: three skeleton rows, `aria-busy`;
  - error: "Couldn't load the members." with "Try again", which repeats the
    request; the rest of the page stays usable;
  - only the owner: the owner's row and, for the owner, the line "Only you so
    far. Invite people by their login." above the form; a participant always
    sees at least two rows.

### Invite form (mockup 3, 4)

- Owner only, at the bottom of the panel: field labelled "Invite by login"
  (visible label), button "Invite" (primary; full width in the 280 px panel).
- Checks before sending, on submit and then while typing: empty after
  trimming "Enter a login."; over 32 characters "Use 32 characters or
  fewer." Nothing is sent while a check fails. The login is sent trimmed.
- While the request runs the button shows the spinner and ignores clicks.
- Success (201): the field clears and keeps the focus, the member appears at
  the end of the list (the list is refreshed from the API), toast
  "<login> added to the project".
- Errors, shown under the field (`aria-describedby`, `aria-invalid`), the typed
  login stays:
  - 404 `User not found` → "No user with that login. Logins are
    case-sensitive.";
  - 409 `User is already a participant of this project` → "<login> is already
    a member.";
  - 409 `You already own this project` → "That's your login. You already own
    this project.";
  - 403 → "Only the owner can invite people.";
  - 422 → the API's message for the field, or "Check the login and try
    again.";
  - network or 500 → "Couldn't invite <login>. Try again.";
  - 404 `Project not found` → toast "This project no longer exists." and go to
    `/projects` (as F2).

### Remove a participant (mockup 5)

- "Remove" opens an alert dialog: title "Remove <login>?", text "<login> loses
  access to **<project>** and its documents. You can invite them again
  later.", buttons "Cancel" and "Remove" (danger).
- Success (204): the dialog closes, the row disappears (the list is refreshed),
  toast "<login> removed from the project", focus moves to the "Members"
  heading (the button that opened the dialog is gone).
- Errors:
  - 404 `Participant not found` → treated as done: close, refresh, toast
    "<login> is no longer a member.";
  - 404 `Project not found` → toast "This project no longer exists." and go to
    `/projects`;
  - 403 → "You don't have permission to do this." in the dialog;
  - network or 500 → "Couldn't remove <login>. Try again." in the dialog.

### Leave a project (mockup 5)

- "Leave project" (participant) opens an alert dialog: title "Leave this
  project?", text "You lose access to **<project>** and its documents. Only
  the owner can invite you back.", buttons "Cancel" and "Leave project"
  (danger).
- The call is `DELETE /project/<id>/members/<own id>`; the own id comes from
  `useMe`. While it is unknown the confirm button is busy.
- Success (204): go to `/projects`, toast "You left <project>", the project is
  gone from every tab (lists refreshed, the project's cached data removed).
- Errors:
  - 404 (either text) → toast "You no longer have access to this project." and
    go to `/projects`;
  - 409 → "The owner can't leave the project." in the dialog;
  - network or 500 → "Couldn't leave the project. Try again." in the dialog.

### Dialogs

Both use `ui/Dialog` like F2: modal, focus moves in and stays in, Esc and
"Cancel" close, focus returns to the opener (except after a successful remove,
see above). On a phone they rise from the bottom with full-width buttons.

### Words

All copy is above and in the mockup. Same action, same name: "Invite" →
"<login> added to the project"; "Remove" → "<login> removed from the project";
"Leave project" → "You left <project>". Sentence case, no "please", no
"successfully", no exclamation marks (`style.md`).

## Acceptance criteria

Behaviour is proven by component tests (Vitest, API mocked) and end-to-end tests
(Playwright against the real stack, each test creating its own users through
`POST /auth`, axe WCAG 2.1 AA on every page and open dialog).

| # | Given / when / then | Proven by |
|---|---|---|
| 1 | Given a project with an owner and participants, when a member opens the project page, then the members panel lists them owner first, each with avatar, login, role badge, " (you)" on their own row, and the count | component, e2e |
| 2 | Given the members request is slow or fails, then skeleton rows show, and on failure "Couldn't load the members." with "Try again" that repeats the request, while the banner and details stay | component |
| 3 | Given the owner, when they type an existing login and click "Invite", then the user appears at the end of the list, the field is empty and focused, and the toast "<login> added to the project" shows | component, e2e |
| 4 | Given the invite field is empty, blank or over 32 characters, when the owner clicks "Invite", then the field shows its message and nothing is sent | component |
| 5 | Given the API answers 404 `User not found`, 409 (either text), 403, 422 or the network fails, then the matching message shows under the field and the typed login stays | component, e2e (unknown login) |
| 6 | Given an invite answered with 404 `Project not found`, then the toast "This project no longer exists." shows and `/projects` opens | component |
| 7 | Given a participant opens the project, then they see the members, the Participant badge, "Edit" and "Leave project", and no invite form, no "Remove", no "Delete project"; the project is in their "Shared with me" tab | component, e2e (F2 criterion 10) |
| 8 | Given the owner, when they click "Remove <login>" and confirm, then the participant is gone from the list, the toast "<login> removed from the project" shows and the focus is on the "Members" heading; "Cancel" changes nothing | component, e2e |
| 9 | Given a remove answered with 404 `Participant not found`, 404 `Project not found`, 403 or a network error, then the matching result from "Remove a participant" shows | component |
| 10 | Given a participant, when they click "Leave project" and confirm, then `/projects` opens with the toast "You left <project>" and the project is gone from every tab | component, e2e |
| 11 | Given a leave answered with 404, 409 or a network error, then the matching result from "Leave a project" shows | component |
| 12 | Given the owner is the only member, then the panel shows the owner's row and "Only you so far. Invite people by their login." | component |
| 13 | Dialogs: focus moves in, stays in, Esc and Cancel close, focus returns to the opener | component, e2e (keyboard) |
| 14 | Every page and open dialog visited in e2e has no WCAG 2.1 AA violation, the invite error included | e2e axe |
| 15 | At 375 px the members panel is under the details, nothing scrolls sideways, a 32-character login fits | e2e at 375 px, screenshots |
| 16 | Lint, type check, component tests, production build and `npm audit --audit-level=high` pass; CI jobs `frontend` and `e2e` are green | commands, CI |
| 17 | No backend file changes: `git diff --stat origin/main...` lists only allowed paths | command |

## Planner's calls

Settled after the builder check (2026-11-15), without changing what is built:

- Who sees the invite form, "Remove" and "Leave project" is decided by
  `my_role` from the project (`GET /project/<id>/info`), never by the members
  list or `useMe`, so a slow or failed members request cannot show an owner's
  control to a participant. `useMe` only marks " (you)" and gives the own id
  for leaving.
- After a 201 the returned member is added to the cached list at once and the
  list is then refreshed from the API; a failed refresh keeps the added row.
- After a successful leave the app goes to `/projects` first, then drops the
  cached project and its members (so the page does not refetch into "Project
  not found") and refreshes every projects list.
- A 404 or 409 whose text is not one of the known ones gets the generic
  message of that action ("Couldn't invite <login>. Try again.", and so on).
- A 422 on remove or leave (an id that is not a UUID) is handled like 404
  `Project not found`, as F2 does for the project page.
- A participant's "Edit" stays: epic 4 lets participants edit (F2).

## Left to the builder

- Component, hook and file names (the parent design suggests
  `frontend/src/members/`).
- Query keys (for example `["members", projectId]`) and how the list is
  refreshed after invite, remove and leave.
- Whether the remove and leave dialogs share one component.
- The spinner and icons from `lucide-react`, as in F2.

## Carried to later epics

- F1b: display names and picked avatars in the panel.
- F4: documents in the left column under the details.
- F5: "Send a link by email" under the invite form (owner).
