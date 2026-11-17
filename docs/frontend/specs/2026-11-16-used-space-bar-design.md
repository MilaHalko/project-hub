# Used-space bar (F4 follow-up for epic 7a)

Status: decided by the builder on 2026-11-16. The user asked for the work to
run without questions, so the calls below are the builder's, made from
`docs/frontend/style.md`, the parent design ("Used space") and the 7a design.

## Intent

Epic 7a gives every project response `storage_used_bytes` and
`storage_limit_bytes`, and the API refuses an upload or replacement that would
pass the limit with `413 {"detail": "Project storage limit reached: … used,
this upload needs …"}`. The project page shows how full the project is, so
people see the limit before they hit it, and when they do hit it they read
what happened and what to do.

## Goals

- The project page shows "18 of 50 MB used" with a 6 px bar, inside the
  documents section next to the upload zone (the place `look.html` puts it).
- The bar is violet; above 80 % it is `warn`. At or over the limit the text
  adds "Limit reached" and the upload hint says "Delete documents to make
  room."
- It is not rendered at all while either field is missing from the project
  response (an older API): no stub, no zero, no fake numbers.
- It follows uploads, replacements and deletes without a reload: the project
  query is already invalidated after each document change
  (`documentsCache.ts`); a 413 also invalidates it, because someone else may
  have filled the project.
- A 413 for the project limit shows on the failed file's row: the file name,
  "Not enough space", the API's numbers, and "Delete documents to make room."
  A 413 for the single-file limit (10 MB) keeps today's message.
- Both roles see the bar (participants upload too).

## Accessibility

- The bar is `role="meter"` with `aria-valuemin=0`, `aria-valuemax=limit`,
  `aria-valuenow=min(used, limit)` and `aria-valuetext="18 of 50 MB used"`,
  labelled "Space used". The visible text says the same, so colour is never
  the only signal ("Limit reached" is text).
- A refused upload is announced through the upload zone's existing live
  region.

## Number format

Megabytes (1 MB = 1 048 576 bytes, as the API's own messages count): whole
numbers from 10 MB up, one decimal below 10 MB, "0 MB" for nothing, and
"less than 0.1 MB" for 1 byte to 0.1 MB. The limit is shown the same way
("50 MB", "1.5 MB"). Used above the limit (the limit was lowered) shows the
real number ("60 of 50 MB used") with a full bar. The shown amount never equals
the shown limit unless the limit is really reached: when used is below the
limit but rounds to it, the amount is rounded down to one decimal ("49.9 of
50 MB used", "2.9 of 3 MB used"). The 413 message uses the same rule.

## States

| State | What the user sees |
|---|---|
| Project loading | Nothing in the bar's place (the documents skeleton covers the section) |
| Fields missing | No bar, no text |
| Under 80 % | Violet bar, "18 of 50 MB used" |
| 80 % to under 100 % | `warn` bar, same text |
| At or over 100 % | `warn` bar, full, "50 of 50 MB used · Limit reached", hint "Delete documents to make room." |
| Upload refused with 413 (limit) | The file's row: "Report.pdf: not enough space. 49 of 50 MB used, this file needs 3 MB. Delete documents to make room." A refused replacement shows the same sentence in its error toast. |
| Upload refused with 413 (file over 10 MB) | Today's message, unchanged |

## Acceptance criteria

1. Given a project response with both fields, when the project page opens,
   then "N of L MB used" and a meter labelled "Space used" with those values
   are shown. (component test)
2. Given a response without the fields, then no meter and no "used" text are
   rendered. (component test)
3. Given used ≥ 80 % of the limit, then the meter has the warning style; at or
   over 100 %, "Limit reached" and "Delete documents to make room." are shown.
   (component test)
4. Given the number format rules above, then the formatter returns the
   expected strings for 0, 1 byte, 0.1 MB, 9.95 MB, 10 MB, 18 MB, 50 MB.
   (unit test)
5. Given a real project, when a file is uploaded, replaced with a bigger one,
   and deleted, then the shown number follows each change without a reload.
   (end-to-end test against the real API)
6. Given a project close to its limit, when a file that does not fit is
   uploaded, then the file's row shows the "not enough space" message with
   "Delete documents to make room.", the other files in the batch still
   upload, and the bar keeps the right number. (component test for the
   message; end-to-end test with a small limit set in `frontend/compose.yml`)
7. Every page visited by the new end-to-end tests passes the axe-core WCAG 2.1
   AA check. (end-to-end)

## Approaches

1. **Read the numbers from the project query (chosen).** The page already
   loads `GET /project/<id>/info` and refreshes it after each document
   change. No new request, always the API's own number.
2. Add up `documents[].size` in the browser. Rejected: the limit still needs
   the API, and the stored total can differ from the list (the Lambda counts
   S3), so the page would show a number the API does not use.
3. Poll the project every few seconds. Rejected: refetch after own changes is
   enough; another member's upload shows on the next visit or focus.

## Extras considered, not built

- **Space column in the projects list** (`look.html` has one; `GET /projects`
  items now carry the fields). Useful, cheap, but outside the handoff's scope;
  proposed for a later frontend task.
- **Refuse a file in the browser when it cannot fit** before uploading it.
  Saves one request, but the API is the authority and another member can free
  or fill space at any time; the 413 path covers it.
- **Image previews from epic 7b.** The F4 design rejected previews in the
  browser; showing them is a separate frontend task once 7b lands.

## Non-goals

- Any backend change. The numbers and the 413 already exist on the 7a branch.
- Per-user quotas, or changing the limit from the web app.

## Review of the look

Mockup: [`mockups/f4b-used-space.html`](../mockups/f4b-used-space.html). The
user is not asked; `design:design-critique` and `design:ux-copy` are the gate
(2026-11-16).

Placement: the block (text, then the 6 px bar, 220 px wide) sits on the right
of the "Documents" heading, above the upload zone, so the number is read
before files are chosen; under 560 px of section width it drops below the
heading and takes the full width. `look.html` put the number inside the drop
zone's line; a separate block keeps the zone's text short and gives the bar
room.

Critique findings and what was done:

| Finding | Severity | Done |
|---|---|---|
| "Tiny files only": a 0.4 % fill is invisible, so the bar looks empty while the text says something is stored | minor | the fill has a 4 px minimum width whenever anything is stored |
| The `warn` orange (#e0821b) is 2.85:1 on white, under the 3:1 asked of graphics | minor | not changed: the bar is never the only signal; the text gives the numbers and "Limit reached" is written out (WCAG 1.4.11 applies to graphics needed to understand the content) |
| At the limit the zone still says "PDF or DOCX, up to 10 MB each", which suggests an upload could work | moderate | the hint becomes "Delete documents to make room." while the project is at or over the limit |
| The refused row repeats the file name (bold title and the message) | minor | kept: every upload error in F4 starts with the name, and the live region reads only the message, so the name must be in it |
| Text and meter say the same thing to a screen reader twice | minor | the visible sentence is hidden from assistive tech (`aria-hidden`); the meter's value text carries it, plus "Limit reached" when it shows |
| Hierarchy: heading first, number second, zone third; the block does not compete with the heading (12 px muted) | works | — |

UX copy (`design:ux-copy`):

- Meter: "18 of 50 MB used"; tiny: "Less than 0.1 MB of 50 MB used"; full:
  "50 of 50 MB used · Limit reached". Accessible name "Space used".
- Refused file: "Report.pdf: not enough space. 49 of 50 MB used, this file
  needs 3 MB. Delete documents to make room." "this file needs" replaces the
  API's "this upload needs": each request carries one file, and "file" is the
  word on the row. The name prefix and lower-case start match the other F4
  errors ("Scan.pdf: file is larger than 10 MB"). The numbers are the API's,
  re-formatted with the bar's rules (the API writes "218 bytes" for sizes that
  are not whole megabytes). If the API's sentence cannot be read, the message
  is "Report.pdf: not enough space. Delete documents to make room."
- Zone hint at the limit: "Delete documents to make room." (what happened is
  already said by "Limit reached" right above).

## Plan

Executed inline (Native), test first in each slice; one commit per slice.

1. **Show how much space a project uses on its page.** `Project` gets the two
   optional fields; `formatMegabytes` and `usedText` in
   `frontend/src/documents/space.ts` (unit tests: AC 4); `SpaceUsed` meter in
   the documents heading row, `ProjectPage` passes the numbers, the upload
   zone's hint changes at the limit (component tests: AC 1–3); e2e in
   `frontend/e2e/space.spec.ts`: upload, replace with a bigger file, delete,
   the number follows, axe on each state (AC 5, 7).
2. **Say why an upload did not fit in the project.** `uploadErrorMessage`
   turns the 413 limit detail into the message above, the single-file 413
   keeps its text; the upload queue and the replace flow invalidate the
   project query after a 413; the batch goes on (component tests: AC 6). The
   e2e stack sets `APP_PROJECT_MAX_BYTES=3145728` (3 MB) in
   `frontend/compose.yml`: above the largest existing e2e upload (2 MB plus
   218 bytes) and shown as a whole number. The e2e test fills a project with
   2 MB through the API, then uploads a 1.5 MB PDF and the 218-byte sample in
   one batch: the first is refused with the message, the second is saved, the
   bar shows the new total (AC 6, 7).
3. **Docs.** `docs/frontend/roadmap.md`: the used-space row is done on
   `feat/used-space-bar`, folded into slice 2, since the roadmap line names both the bar and the 413 message.

## Constraints

- Only `frontend/`, `docs/frontend/` and the "Frontend requests" rows of
  `docs/PRDs/roadmap.md` change. The test limit goes in `frontend/compose.yml`
  (an override for the e2e stack), not in the root `docker-compose.yml`.
- The branch is stacked on `feat/lambda-size-quota` until that is merged.
