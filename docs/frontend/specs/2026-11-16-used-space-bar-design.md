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
real number ("60 of 50 MB used") with a full bar.

## States

| State | What the user sees |
|---|---|
| Project loading | Nothing in the bar's place (the documents skeleton covers the section) |
| Fields missing | No bar, no text |
| Under 80 % | Violet bar, "18 of 50 MB used" |
| 80 % to under 100 % | `warn` bar, same text |
| At or over 100 % | `warn` bar, full, "50 of 50 MB used · Limit reached", hint "Delete documents to make room." |
| Upload refused with 413 (limit) | The file's row: "Report.pdf: not enough space. 49 MB of 50 MB used, this upload needs 3 MB. Delete documents to make room." |
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

## Constraints

- Only `frontend/`, `docs/frontend/` and the "Frontend requests" rows of
  `docs/PRDs/roadmap.md` change. The test limit goes in `frontend/compose.yml`
  (an override for the e2e stack), not in the root `docker-compose.yml`.
- The branch is stacked on `feat/lambda-size-quota` until that is merged.
