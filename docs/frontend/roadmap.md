# Frontend roadmap

Date: 2026-11-14
Status: approved by the user (2026-11-14)

High-level epics (F0–F6, with F1b) for the web frontend described in
[`2026-11-14-frontend-design.md`](2026-11-14-frontend-design.md). The frontend is
an addition beyond the spec; the backend plan lives in
[`docs/PRDs/roadmap.md`](../PRDs/roadmap.md) and is not repeated here.

## Ground rules

- Everything in the backend roadmap's ground rules still applies: the spec is the
  source of truth, endpoint names never change, the spec is the floor and every
  extra is proposed, argued and decided by the user.
- Every frontend epic goes through the project skill `add-frontend-feature`
  (`.claude/skills/add-frontend-feature/SKILL.md`): brainstorm → look → worktree →
  plan → TDD → verify (with screenshots, axe and the security checklist) →
  review. Its design doc goes to `docs/frontend/specs/`, its plan to
  `docs/superpowers/plans/`.
- A frontend epic starts only when the API epic it depends on is merged into
  `main`. Frontend work never changes the backend: no code in `src/`, `tests/`,
  migrations, `pyproject.toml`, `poetry.lock`, the root `Dockerfile` or
  `docker-compose.yml`, or `.github/workflows/ci.yml`. A backend change the UI
  needs (for example `users.avatar` for F1b) is a separate backend task, built
  with the `add-feature` skill in its own session, branch and PR, and merged
  before the frontend epic that needs it (user, 2026-11-14).
- What the UI needs from the API but no API epic has agreed to build is listed
  in the backend roadmap's [Frontend requests](../PRDs/roadmap.md#frontend-requests)
  section, so API epics see it.
- Phone layout (375 px) is part of every epic, not a separate one.

## Epics

| # | Epic | Scope | Depends on |
|---|---|---|---|
| F0 | ✅ Scaffold and shell (PR #14) | `frontend/` with Vite, React, TypeScript, ESLint, Prettier, Vitest, Playwright with `@axe-core/playwright`; workflow `frontend.yml` with jobs `frontend` and `e2e`; `frontend/Dockerfile` (Node build, then nginx) with the SPA fallback, cache headers, security headers (CSP, `Referrer-Policy`, `nosniff`) and the API proxied under `/api/`; `frontend/compose.yml` adding the `web` service; no backend change; style tokens and self-hosted fonts; app shell: sidebar layout, global loader bar, toasts, not-found page. Proven by a first end-to-end test that opens the app with the axe check | the tooling PR #9 (`add-frontend-feature` skill) merged and the plugins `frontend-design`, `design`, `playwright` installed; no API epic |
| F1 | ✅ Sign in and profile (PR #19) | Register, log in, log out, session expired on 401, token in `sessionStorage`, guarded routes; profile page with password change. Default avatars derived from the user id (frontend only) | F0, 3 ✅ |
| F1b | Avatar picker | Frontend only: picker on the profile page that saves through `PATCH /users/me`; avatars (and the display name, if accepted) shown wherever a user appears | F1; the backend task "users: avatar and display name" merged (it needs 4 for the migration order and the `owner` object) |
| F2 | ✅ Projects (PR #20) | Projects list with tabs All / Owned / Shared with me, "Show more" paging, empty state; create and edit project; project page with the holographic header; delete for the owner only, with confirmation | 4 |
| F3 | ✅ Members and invites (PR #27) | Invite by login (owner only); members panel with avatars and roles | 5 (members list comes with 4) |
| F4 | ✅ Documents (PR #32) | Upload (drag and drop or picker, pdf/docx), list with sizes, download, replace, delete with confirmation; the used-space bar appears by itself when 7a adds the fields | 6 (space bar: 7a) |
| F5 | Share and join | "Send a link by email" form (owner); join landing page `/join` on the web app; the API `GET /join` answers a browser without a sign-in with `303` to this page (epic 10 chose it) | 10 |
| F6 | Ready for the defense | One end-to-end test for the whole demo scenario (two users, eight steps); phone-width pass on every screen; `design:accessibility-review`; README section "How to demo" (UI part and Swagger part) | F1–F5; before checkpoint 4 (final demo) |

## Order and parallel work

```
PR #9 ─→ F0 ─→ F1 ─→ F2 ─┬→ F3 ─→ F5
               ↑     ↑   │   ↑      ↑
               3     4   │   5      10
                     ↓   └→ F4
                     U       ↑
                     ↓       6  (space bar: 7a)
                    F1b

U = backend task "users: avatar and display name" (add-feature, own PR)
F1b, F3, F4, F5 ─→ F6 (before the final demo)
```

- F0 needs no API epic, only the tooling PR #9 merged (the workflow skill F0
  must follow lives there). It can run in parallel with epic 4.
- F1 follows F0; epic 3 is already merged and F1 changes no backend code.
- F1b (avatars) only uses the API. It waits for the backend task "users:
  avatar and display name", which adds a `users` migration and so waits for
  epic 4 (migration `0003` and the `owner` object). F1b can run in parallel
  with F2.
- After F2 the branches `F3 → F5` and `F4` are independent, like `5 → 10` and
  `6 → 7` in the backend roadmap, and can run in parallel sessions.
- Two sessions never edit the same files at the same time: the backend epic and
  the frontend epic that depends on it run one after another, not together. Only
  one session at a time adds a database migration.

## What each screen needs from the API

| Screen or element | API | Backend epic | Status |
|---|---|---|---|
| Register, log in, log out, profile, password change | `POST /auth`, `POST /login`, `POST /logout`, `GET /users/me`, `PUT /users/me/password` | 3 | ✅ merged |
| Avatar picker and avatars everywhere | `users.avatar`, `PATCH /users/me` | a backend task with `add-feature`, after 4, before F1b | planned |
| Projects list, tabs, paging | `GET /projects?role=&limit=&offset=` | 4 | in progress |
| Project page, edit, delete | `GET/PUT /project/<id>/info`, `DELETE /project/<id>`, `my_role` | 4 | in progress |
| Members panel | `GET /project/<id>/members` → `[{id, login, role, joined_at}]`, owner first | 4 | accepted in epic 4 |
| Invite form | `POST /project/<id>/invite?user=<login>` | 5 | planned |
| Documents list, upload, download, replace, delete | spec document endpoints; size, type and upload date in the metadata; how download works | 6 | planned |
| Used-space bar | used and limit values in project responses | 7a | planned; hidden until then |
| Share form, join page | `GET /project/<id>/share?with=<email>`, `GET /join` browser flow (`303` to the web page) | 10 | accepted |
| Summary counters above the list | totals for projects, documents, space | — | later |
| Delete account dialog | `DELETE /users/me` with 409 "Delete your projects first" | after 6 | later |

## Future improvements (not scheduled)

Recorded so they are not proposed again by accident; each needs the user's yes
before it is built.

- **Upload your own avatar picture.** Needs an S3 upload path, image type and
  size checks, and possibly the 7b resize Lambda. Preset avatars stay as the
  default.
- **Delete account.** When `DELETE /users/me` exists (planned after epic 6): a
  user who still owns projects gets 409 (`projects.owner_id` is `ON DELETE
  RESTRICT`). The UI shows a dialog that explains the account still owns
  projects and cannot be deleted yet, with a link to "My projects"
  (`/projects?role=owner`, backed by `GET /projects?role=owner`), so a
  delete never looks like a silent failure. Requested by the user via epic 4.
- **Search in the projects list.** Client-side filter of loaded projects.
- **Upload progress bar.** Needs `XMLHttpRequest` (`fetch` reports no upload
  progress).
- **Dark theme.** Second set of tokens; every axe and contrast check runs twice.
- **Summary counters** (projects, documents, space used) above the list, once
  the API returns totals.

Rejected: PDF preview in the browser (cost, no docx), a second UI language.

## Open questions

| Question | Decided in |
|---|---|
| HTTPS on the ALB: own domain with ACM, self-signed, or HTTP for the demo | backend 8a |
| Document download: through the API or a presigned S3 URL | backend 6 |
| Direct browser upload to S3 (needs a bucket CORS rule) or through the API | backend 6 |
| `GET /join`: the API redirects a browser to the web app's `/join` page (`303`) | backend 10 (decided) |
| Cloud hosting of the frontend: S3 static site or a second container; it does not touch backend 8a and 8b | frontend, after F6 |
| Share by email: owner only, like invites? | backend 10 |
