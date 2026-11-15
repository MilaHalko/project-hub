# F4 — Documents

Date: 2026-11-15
Status: approved by the user (2026-11-15)
Parent design: [`../2026-11-14-frontend-design.md`](../2026-11-14-frontend-design.md)
Roadmap row: [`../roadmap.md`](../roadmap.md) (F4)
Mockup: [`../mockups/f4-documents.html`](../mockups/f4-documents.html) (open in a browser)
API: epic 6 (PR #21), `src/project_hub/documents/`

## Intent

Everyone in a project keeps its files on the project page: they upload a pdf or
docx, see the list with sizes, download a file, replace it with a new version
and delete it. These are steps 3 and 6 of the defense demo. The API exists
(epic 6, merged); this epic only calls it.

## Goals

- A "Documents" section on the project page, under Details.
- Upload by drag and drop or a file picker, several files at once, one request
  per file, so a bad file fails alone and the good ones are saved.
- A list with type tile, name, size, uploader and date, newest first.
- Download, replace and delete (with a confirmation dialog) on every row.
- Owner and participant see the same section: the API lets both do all of it.
- Every state at 1280 px and 375 px.

## Non-goals

- The used-space bar (epic 7a). No stub, no placeholder: it is added when the
  API returns the numbers.
- An upload progress bar (`fetch` reports no upload progress; roadmap "Later").
- Preview in the browser (rejected in the parent design), rename, folders.
- Anything in the backend.

## Anti-goals

- A file that fails without a visible message that names it.
- A bad file in a batch that stops the good ones.
- A delete with one click and no confirmation.
- The token in a URL (a download link with `?token=`).
- A 10 MB file that works through Swagger but fails through the web app.

## Constraints

- API facts (epic 6):
  - `GET /project/<id>/documents` → `[{id, project_id, name, content_type,
    size, uploaded_by: {id, login} | null, created_at, updated_at}]`, newest
    `created_at` first; `uploaded_by` is `null` when the account no longer
    exists; `created_at` is the first upload, `updated_at` the last replace;
  - `POST /project/<id>/documents`, multipart field `files` → 201 with the
    list; `PUT /document/<id>`, field `file` → 200, same `id` and
    `created_at`, so the row keeps its place in the list; pdf ↔ docx allowed;
  - `GET /document/<id>` → the bytes with `Content-Disposition`; it needs the
    Bearer header, so the app fetches it and saves the blob;
  - `DELETE /document/<id>` → 204;
  - errors are one string in `detail` and name the file: 422 `"<name>: only
    pdf and docx documents are allowed"`, `"<name>: content is not a valid
    pdf"`, `"<name>: file is empty"`; 413 `"<name>: file is larger than 10
    MB"` or `Request is too large`; 411/400 for a missing or bad
    `Content-Length`; 503 `File storage is unavailable`; 404 `Project not
    found` / `Document not found` when there is no access;
  - any document change touches the project's `updated_at`, and `GET
    /projects` items carry `documents`.
- nginx in `frontend/` proxies `/api/` with its default 1 MB body limit, so
  any file over 1 MB would get nginx's own 413 before reaching the API. The
  proxy gets `client_max_body_size 11m`: the API's own limit for one file is
  10 MB plus 1 MB for the form.
- Frontend rules: only `frontend/`, `docs/frontend/` and the roadmap's
  "Frontend requests" section change. F3 (PR #27) also edits the project page;
  this epic adds one line there and keeps the rest in `src/documents/`.

## Approaches

### Upload

| Option | Trade-off | Decision |
|---|---|---|
| **One request per file, one after another** | A bad file fails alone with its own message; each file has its own status; a little slower for many files | **Chosen** (agreed in epic 6) |
| All files in one request | One round trip, but the API is all or nothing: one bad file stops the whole batch | Rejected |
| Several requests at the same time | Faster, but statuses jump around and a slow connection gets crowded | Rejected |

### Download

| Option | Trade-off | Decision |
|---|---|---|
| **`fetch` with the Bearer header, then save the blob** | Works with the API as it is; the file passes through memory (at most 10 MB) | **Chosen** |
| `<a href="/api/document/<id>">` | Simplest, but a link cannot carry the header, so it gets 401 | Rejected |
| Token in the query string | Leaks the token into logs and history | Rejected (anti-goal) |

### Replace

| Option | Trade-off | Decision |
|---|---|---|
| **"Replace" opens the file picker; the chosen file replaces at once** | Picking a file is already a deliberate second step; one dialog fewer | **Chosen** (user, 2026-11-15) |
| Picker, then a confirmation dialog | One more click for every replace | Rejected |

### List markup

| Option | Trade-off | Decision |
|---|---|---|
| **A list (`ul`) with one row per file** | One markup for desktop and phone, the CSS changes the layout; rows read well in a screen reader | **Chosen** (builder's call) |
| A table on desktop and cards on phone (as in F2) | Two markups to keep in sync for five fields | Rejected |

## Additions beyond the roadmap row

| Addition | Why | Cost | Recommendation |
|---|---|---|---|
| "Documents" column in the projects list (count) | The data already comes in `GET /projects`; the list shows which project has files; it is in the approved look (`look.html`) | Small: one column, a component test, an e2e assertion | **Accepted** (user, 2026-11-15) |
| "Retry" on a failed upload | One click instead of picking the file again | Small, but most failures are a bad file that fails again | **Rejected** (user, 2026-11-15) |

## Design

### Section (mockup 1, 2)

- Under Details: an `h2` "Documents" with the count in a small grey badge, the
  upload zone, then the list. With F3 merged the section sits in the left
  column of the page grid, under Details.

### Upload zone (mockup 1, 3, 4)

- Dashed violet border on light violet (style.md). Text: "Drop PDF or DOCX
  files here or **Choose files**" and a second line "PDF or DOCX, up to 10 MB
  each".
  "Choose files" is a real button that opens a hidden
  `<input type="file" multiple accept=".pdf,.docx">`.
- While files are dragged over it, the zone turns solid violet with "Drop to
  upload". Dropping on the rest of the page does nothing (the browser would
  otherwise open the file and leave the app).
- On a touch screen (no hover) only "Choose files" and the second line show
  (no drag on touch); one label keeps one accessible name in every layout.
- Each chosen file is checked first in the browser: extension `.pdf` or
  `.docx` (any case), not empty, at most 10 MB. A failing file is not sent and
  gets the same message the API would give.
- Files go one after another. While a batch runs, a list of uploads shows
  under the zone: tile, name, size, and "Waiting" or "Uploading…" with a
  spinner. A finished file leaves this list and appears in the documents list.
  A failed file stays with its error in danger colour and a "Dismiss" button.
- One toast when the batch ends: "File uploaded" or "3 files uploaded" (only
  the saved ones). A screen reader hears each error (live region).
- Files chosen while a batch runs join the end of the queue. If no file of a
  batch was saved, there is no toast: the errors are already on screen.

### List (mockup 1, 2)

- Each row: type tile (PDF light red, DOCX light blue, 34 px), the name
  (wraps, never cut) with a line under it "Added Nov 12 by alex", or "Updated
  yesterday by alex" when `updated_at` differs from `created_at`; the uploader
  is "a deleted account" when `uploaded_by` is `null`; exact time on hover. The
  size ("2.4 MB") in its own column.
- Actions on the right: "Download", "Replace", "Delete" as small secondary
  buttons; their accessible names carry the file name ("Download Client
  brief.pdf"). When the section is narrower than about 560 px (a phone, or a
  narrow window beside the members panel) the actions move to a row under the
  name, at least 40 px tall for touch (a container query, so it follows the
  section's width, not the window's).
- Loading: three skeleton rows. Error: "Couldn't load the documents." with
  "Try again". Empty: "No documents yet" and "Upload the first one above."

### Download

- The button shows a spinner while the file comes; the blob is saved under the
  document's name through a temporary object URL, which is released at once.
- 404: toast "This document no longer exists. Someone may have deleted it."
  and the list reloads. Other
  failure: toast "Couldn't download <name>. Try again."

### Replace (mockup 5)

- Opens the picker for one file; the same browser checks as upload; then
  `PUT`. The row shows "Replacing…" with a spinner and keeps its place.
- Success: toast "File replaced"; the row shows the new name, size and
  "updated just now". Failure: toast with the API message; 404 as in download.

### Delete (mockup 6)

- `ui/Dialog` as an alertdialog: title "Delete this document?", text "This
  deletes <name> for everyone in the project. You can't undo this.", buttons
  "Cancel" and "Delete document" (solid danger). No typed confirmation: one
  file is a smaller loss than a project.
- Success: the dialog closes, the row goes, toast "Document deleted". 404:
  the same, with the "no longer exists" toast. Other failure: the message
  inside the dialog, which stays open.

### Data

- Query `["documents", projectId]`, 30 s `staleTime` like the project page.
- After an upload, replace or delete the list is updated from the answer, and
  `["project", id]` and every `["projects", …]` list are refreshed (the
  project's `updated_at` and its `documents` changed).

### Words

Sentence case, verbs on buttons, no "please", no "successfully". Messages from
the API are shown as they come: they already name the file and say what is
wrong. Own messages: 503 "File storage is unavailable. Try again later.";
network down "<name>: couldn't upload. Check your connection and try again."

## Acceptance criteria

1. Given a project page, when it loads, then the Documents section lists the
   project's files newest first with type, name, size, uploader and date
   (component; e2e).
2. Given no documents, then the section says "No documents yet" (component; e2e).
3. Given the list fails to load, then "Couldn't load the documents." and "Try
   again" reloads it (component).
4. Given a pdf chosen in the picker, when it uploads, then it appears in the
   list and a toast says "File uploaded" (component; e2e with axe).
5. Given a docx dropped on the zone, then it uploads the same way (component; e2e).
6. Given three files where one is a `.txt`, then the two good ones are saved
   and the `.txt` shows "only pdf and docx documents are allowed" without a
   request (component).
7. Given a file over 10 MB or an empty file, then it is not sent and shows
   the API's wording (component).
8. Given a file with a pdf name but other content, then the API's 422 message
   shows on that file and "Dismiss" removes it (component; e2e).
9. Given a 503 or no network, then the upload shows its own message (component).
10. Given a 2 MB pdf, when it uploads through the web container, then it is
    saved (e2e, proves the nginx body limit).
11. Given a document, when "Download" is clicked, then the browser saves a file
    with the document's name and the same bytes (component: blob saved; e2e:
    download event and content).
12. Given a document, when "Replace" gets a docx, then the row keeps its place
    with the new name and size and a toast says "File replaced" (component; e2e).
13. Given a document, when "Delete" is confirmed, then the row goes and a toast
    says "Document deleted"; "Cancel" and Esc keep it (component; e2e with axe
    on the open dialog).
14. Given a document deleted elsewhere, when any action answers 404, then a
    toast says "This document no longer exists." and the list reloads (component).
15. Given a participant, then the same section and actions show (component).
16. Given the projects list, then each row shows its documents count
    (component; e2e).
17. Every page state above passes axe WCAG 2.1 AA at 1280 and 375 px (e2e).

## Left to the builder

- Component and file names inside `frontend/src/documents/`.
- How the API client sends `FormData` and reads a blob (extend `apiFetch` or
  add a sibling next to it), as long as 401 still ends the session.
- Size format: one decimal for MB and KB ("2.4 MB", "820 KB", "512 B").

## Carried to later epics

- Used-space bar: when epic 7a adds the fields to the project responses.
- Upload progress bar: roadmap "Later".
- Participant end-to-end test: F3 brings the invite helper; F4 proves the
  participant view in component tests (the API allows both roles the same).

## Review of the look

Design critique (2026-11-15), fixed in the mockup and above:

- Three actions per row squeezed the name in a narrow column: the actions now
  wrap under the name by the section's own width, not only on phones.
- Phone buttons were about 36 px tall: now at least 40 px.
- "by deleted account" read like a login: now "by a deleted account".
- The 404 toast said what happened but not why: it now adds "Someone may have
  deleted it."
- Kept on purpose: three visible buttons instead of a "⋯" menu (one tap, easy
  to find in the demo, no menu to make accessible); "Delete" in danger colour
  on every row, as on the project page.
