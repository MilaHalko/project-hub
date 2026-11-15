# F4 Documents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (Native, chosen by the user in PR #18) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Documents section on the project page (list, upload by drop or picker, download, replace, delete with confirmation) and a documents count in the projects list.

**Architecture:** A new feature folder `frontend/src/documents/` holds the section, its rows, the upload queue and the delete dialog; `frontend/src/api/documents.ts` wraps the five endpoints. `apiFetch` learns to send `FormData` and a sibling `apiFetchBlob` reads file bytes, both sharing the 401 handling. The project page gets one new line; the nginx proxy gets a body limit that fits a 10 MB file.

**Tech Stack:** React 19, TypeScript, TanStack Query 5, CSS modules, Vitest + Testing Library, Playwright + `@axe-core/playwright`, nginx.

**Spec:** [`docs/frontend/specs/2026-11-15-f4-documents-design.md`](../../frontend/specs/2026-11-15-f4-documents-design.md), mockup [`docs/frontend/mockups/f4-documents.html`](../../frontend/mockups/f4-documents.html).

## Global Constraints

- Only `frontend/` and `docs/` change; never `src/`, `tests/`, root `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `poetry.lock`, `.github/workflows/ci.yml`.
- No new comments or docstrings; check every diff for new `//`, `/*`, `#` lines before committing.
- Copy (exact): zone "Drop PDF or DOCX files here or" + button "Choose files", second line "Up to 10 MB each"; touch (`(pointer: coarse)`) button text "Choose PDF or DOCX files"; drag "Drop to upload"; statuses "Waiting", "Uploading…", "Replacing…"; button "Dismiss"; meta "Added <date> by <login>" / "Updated <date> by <login>" with "a deleted account" for `uploaded_by: null` and the date from `formatUpdated`; empty "No documents yet" + "Upload the first one above."; list error "Couldn't load the documents." + "Try again"; toasts "File uploaded", "<n> files uploaded", "File replaced", "Document deleted", "This document no longer exists. Someone may have deleted it.", "Couldn't download <name>. Try again."; dialog title "Delete this document?", text "This deletes <name> for everyone in the project. You can't undo this.", buttons "Cancel" / "Delete document"; own errors "File storage is unavailable. Try again later.", "<name>: couldn't upload. Check your connection and try again.".
- Browser checks use the API's words: "<name>: only pdf and docx documents are allowed", "<name>: file is empty", "<name>: file is larger than 10 MB". Limit `10 * 1024 * 1024` bytes.
- Accessible names of row buttons carry the file name: "Download <name>", "Replace <name>", "Delete <name>" (visible text stays "Download" etc.).
- Cache: query key `["documents", projectId]`, `staleTime: 30_000`; after a change refresh `["project", projectId]` and `["projects"]`.
- One commit per task, plain-words subject, no `Co-Authored-By` trailer.
- e2e runs against the stack `f4docs` (`E2E_BASE_URL=http://127.0.0.1:8094`); every page state visited gets `expectAccessible(page)`; both Playwright projects (desktop and phone) run every test.

## Review Focus

1. Two files with the same name in one batch: each keeps its own status row (keys by a generated id, never by name) — test in Task 2.
2. A 401 in the middle of a batch: the session ends and the rest of the queue is not sent — test in Task 2.
3. Something that is not a file dragged onto the zone (selected text): nothing is queued, no crash — test in Task 2.
4. A double click on "Download", "Replace" or "Delete document": one request — tests in Tasks 3, 4, 5.
5. A file dropped outside the zone: the browser does not open it and leave the app — test in Task 2 (the page-level `dragover`/`drop` default is prevented while the section is mounted).

---

### Task 1: See a project's documents with their sizes

**Files:**
- Create: `frontend/src/api/documents.ts`, `frontend/src/documents/fileRules.ts`, `frontend/src/documents/fileRules.test.ts`, `frontend/src/documents/DocumentsSection.tsx`, `frontend/src/documents/DocumentsSection.module.css`, `frontend/src/documents/DocumentRow.tsx`, `frontend/src/documents/FileTile.tsx`, `frontend/src/documents/DocumentsSection.test.tsx`, `frontend/e2e/documents.ts`, `frontend/e2e/documents.spec.ts`, `frontend/e2e/files/sample.pdf`, `frontend/e2e/files/sample.docx`
- Modify: `frontend/src/projects/ProjectPage.tsx` (render `<DocumentsSection projectId={data.id} />` right after `<Details …/>`), `frontend/src/test/mockApi.ts` (default answer `[]` for `GET /api/project/<id>/documents`, by pattern), `frontend/README.md`

**Interfaces:**
- Produces: `type Document = { id; project_id; name; content_type; size: number; uploaded_by: { id: string; login: string } | null; created_at; updated_at }`; `listDocuments(projectId: string): Promise<Document[]>`; `formatSize(bytes: number): string`; `fileKind(name: string): "pdf" | "docx" | null`; `DocumentsSection({ projectId })`; `DocumentRow({ document, actions })`; e2e `uploadViaApi(request, user, projectId, file: { name: string; mimeType: string; buffer: Buffer }): Promise<{ id: string }>`, `samplePdf`, `sampleDocx` (Buffers read from `e2e/files/`).

- [ ] **Step 1: Failing unit tests** — `fileRules.test.ts`: `formatSize(512) === "512 B"`, `formatSize(839_680) === "820 KB"`, `formatSize(2_516_582) === "2.4 MB"`, `formatSize(1024) === "1 KB"`; `fileKind("A.PDF") === "pdf"`, `fileKind("x.docx") === "docx"`, `fileKind("x.txt") === null`. `DocumentsSection.test.tsx` (through `renderApp("/projects/<id>")` with `mockApi`): heading level 2 "Documents" with the count "2"; rows in API order with name, "2.4 MB", "Added Nov 12 by sam", "Updated yesterday by mila" when `updated_at` ≠ `created_at` (fake timers), "a deleted account" for `uploaded_by: null`, type tiles "PDF"/"DOCX"; empty → "No documents yet" and "Upload the first one above."; a 500 → "Couldn't load the documents." and "Try again" refetches into the list; pending → `role="status"` named "Loading documents"; a participant project shows the same section.
- [ ] **Step 2: Run** `npm test -- documents` — expect failures for missing modules.
- [ ] **Step 3: Implement** the API function, `fileRules.ts`, the section (list `ul` of `DocumentRow`, `h2` with count badge, skeleton, empty, error), `FileTile`, and the one line in `ProjectPage.tsx`. Row layout by container query (`container-type: inline-size` on the section; below 560 px the actions go under the name). Exact time in the `title` of a `<time>`.
- [ ] **Step 4: Run** `npm test` — all green, existing ProjectPage tests included.
- [ ] **Step 5: e2e** — make `sample.pdf` (a minimal valid pdf) and `sample.docx` (zip with `[Content_Types].xml` and `word/document.xml`) once with Python's `zipfile`, commit them; `documents.spec.ts`: "lists uploaded documents with their sizes" (two files through `uploadViaApi`, see names, sizes and the count, axe) and "shows no documents yet" (axe). Run `E2E_BASE_URL=http://127.0.0.1:8094 npx playwright test documents` — green.
- [ ] **Step 6: README** — one paragraph: `e2e/documents.ts` helpers and the documents default in `mockApi`.
- [ ] **Step 7: lint, typecheck, commit** "See a project's documents with their sizes on the project page".

### Task 2: Upload pdf and docx files by picker or drag and drop

**Files:**
- Create: `frontend/src/documents/UploadZone.tsx`, `frontend/src/documents/UploadZone.module.css`, `frontend/src/documents/useUploadQueue.ts`, `frontend/src/documents/documentsCache.ts`, `frontend/src/documents/UploadZone.test.tsx`, `frontend/src/api/client.test.ts` (extend)
- Modify: `frontend/src/api/client.ts` (a `FormData` body is sent as is, without `Content-Type`), `frontend/src/api/documents.ts`, `frontend/src/documents/fileRules.ts` (+test), `frontend/src/documents/DocumentsSection.tsx`, `frontend/nginx/default.conf` (`client_max_body_size 11m;` in `location ^~ /api/`), `frontend/e2e/documents.spec.ts`, `frontend/README.md` (nginx paragraph: the body limit and why)

**Interfaces:**
- Consumes: Task 1's `Document`, `fileKind`, `formatSize`.
- Produces: `uploadDocument(projectId: string, file: File): Promise<Document>` (field `files`, returns the first item); `checkFile(file: File): string | null`; `MAX_FILE_BYTES`; `documentsChanged(queryClient, projectId, update: (docs: Document[]) => Document[]): void` (sets `["documents", id]` and invalidates `["project", id]` and `["projects"]`); `uploadErrorMessage(error: unknown, name: string): string`.

- [ ] **Step 1: Failing tests** — client: a `FormData` body reaches `fetch` unchanged with only the `Authorization` header. `checkFile`: `.txt` → "notes.txt: only pdf and docx documents are allowed"; 0 bytes → "a.pdf: file is empty"; `MAX_FILE_BYTES + 1` → "a.pdf: file is larger than 10 MB"; exactly `MAX_FILE_BYTES` → `null`. `uploadErrorMessage`: 422 string detail → the detail; 503 → "File storage is unavailable. Try again later."; status 0 → "a.pdf: couldn't upload. Check your connection and try again.". `UploadZone.test.tsx`: picker with one pdf → one `POST /api/project/<id>/documents` whose body is `FormData` with `files` = that file, the row appears in the list, toast "File uploaded"; three files (pdf, txt, docx) → two requests in order, toast "2 files uploaded", the txt shows its message and "Dismiss" removes it; while the first request is pending the second shows "Waiting" and the first "Uploading…"; a 422 answer stays as an error row; two files named the same both get rows; a 401 on the first file → the second is never requested; drop of a pdf on the zone uploads it; a drop with no files does nothing; while files are over the zone it reads "Drop to upload"; `dragover` on `document.body` has `defaultPrevented`; all failed → no toast.
- [ ] **Step 2: Run** `npm test` — the new tests fail.
- [ ] **Step 3: Implement** the client change, `uploadDocument`, `checkFile`, `uploadErrorMessage`, `documentsChanged`, `useUploadQueue(projectId)` (items `{ key, file, state: "waiting" | "uploading" | "failed", error? }`, one request at a time, stops on 401, batch toast when the queue empties), and `UploadZone` (hidden `<input type="file" multiple accept=".pdf,.docx">` labelled by the button, drag counter for enter/leave, page-level `dragover`/`drop` prevented in an effect, uploads list with a polite live region for errors). nginx line.
- [ ] **Step 4: Run** `npm test` — green.
- [ ] **Step 5: e2e** — rebuild the stack's `web` image; tests: "uploads a pdf from the file picker" (`setInputFiles`, row and toast, axe with the uploads list visible), "uploads a docx dropped on the zone" (a `DataTransfer` built in the page with `page.evaluateHandle`, dispatched as `dragenter`/`dragover`/`drop`), "shows the API's message for a file that is not a real pdf" (`test.use({ expectedApiStatuses: [422] })`, a `fake.pdf` with text content, message and "Dismiss", axe), "uploads a 2 MB pdf through the web container". Run — green.
- [ ] **Step 6: lint, typecheck, commit** "Upload pdf and docx files to a project by picker or drag and drop".

### Task 3: Download a document

**Files:**
- Create: `frontend/src/documents/saveBlob.ts`, `frontend/src/api/client.test.ts` (extend)
- Modify: `frontend/src/api/client.ts` (`apiFetchBlob(path: string): Promise<Blob>`, same 401 and error handling as `apiFetch`), `frontend/src/api/documents.ts` (`downloadDocument(id): Promise<Blob>`), `frontend/src/documents/DocumentRow.tsx`, `frontend/src/documents/DocumentsSection.tsx`, `frontend/src/test/mockApi.ts` (an answer may carry a `Blob` body sent as is), `frontend/src/documents/DocumentsSection.test.tsx`, `frontend/e2e/documents.spec.ts`

**Interfaces:**
- Produces: `saveBlob(blob: Blob, name: string): void` (object URL, temporary `<a download>`, click, revoke); `apiFetchBlob`.

- [ ] **Step 1: Failing tests** — client: `apiFetchBlob` returns the bytes with the Bearer header; a 404 throws `ApiError(404, "Document not found")`; a 401 ends the session. Section: "Download Client brief.pdf" calls `GET /api/document/<id>` once even on a double click, `URL.createObjectURL` gets the blob, the anchor's `download` is the document name, `revokeObjectURL` is called; 404 → toast "This document no longer exists. Someone may have deleted it." and the list is requested again; 500 → "Couldn't download Client brief.pdf. Try again.".
- [ ] **Step 2: Run** — fail. **Step 3: Implement.** **Step 4: Run** — green.
- [ ] **Step 5: e2e** — "downloads a document under its name": `page.waitForEvent("download")`, `suggestedFilename()` equals the name, the saved bytes equal `samplePdf`. Run — green.
- [ ] **Step 6: lint, typecheck, commit** "Download a project document under its own name".

### Task 4: Replace a document with a new file

**Files:**
- Modify: `frontend/src/api/documents.ts` (`replaceDocument(id: string, file: File): Promise<Document>`, field `file`, method `PUT`), `frontend/src/documents/DocumentRow.tsx`, `frontend/src/documents/DocumentsSection.tsx`, `frontend/src/documents/DocumentsSection.test.tsx`, `frontend/e2e/documents.spec.ts`

- [ ] **Step 1: Failing tests** — "Replace Client brief.pdf" opens a single-file picker; choosing `brief v2.docx` sends one `PUT /api/document/<id>` with `file`; the row shows "Replacing…" without the three buttons while pending, then the new name and size in the same place, toast "File replaced"; a `.txt` is refused with its message as an error toast and no request; 422 → toast with the API's message; 404 → the "no longer exists" toast and a reload; the button's focus returns to the row's "Replace" after success.
- [ ] **Step 2: Run** — fail. **Step 3: Implement** (one hidden single-file input in the row). **Step 4: Run** — green.
- [ ] **Step 5: e2e** — "replaces a pdf with a docx and keeps its place": two documents, replace the older one, it stays second with the new name, toast, axe. Run — green.
- [ ] **Step 6: lint, typecheck, commit** "Replace a project document with a new file".

### Task 5: Delete a document after confirming

**Files:**
- Create: `frontend/src/documents/DeleteDocumentDialog.tsx`, `frontend/src/documents/DeleteDocumentDialog.module.css`, `frontend/src/documents/DeleteDocumentDialog.test.tsx`
- Modify: `frontend/src/api/documents.ts` (`deleteDocument(id): Promise<void>`), `frontend/src/documents/DocumentsSection.tsx`, `frontend/e2e/documents.spec.ts`

- [ ] **Step 1: Failing tests** — "Delete Client brief.pdf" opens an alertdialog "Delete this document?" with the text naming the file; "Cancel" closes it without a request; "Delete document" sends one `DELETE /api/document/<id>` even on a double click, the row goes, the count drops, toast "Document deleted"; 404 → the dialog closes, the row goes, toast "This document no longer exists. Someone may have deleted it."; 500 → "Couldn't delete the document. Try again." inside the dialog, which stays open.
- [ ] **Step 2: Run** — fail. **Step 3: Implement** with `ui/Dialog` (`role="alertdialog"`, `describedBy`), the same "no close while pending" rule as `DeleteProjectDialog`. **Step 4: Run** — green.
- [ ] **Step 5: e2e** — "deletes a document after confirming": Esc keeps it and returns focus to "Delete <name>", then confirm, row gone, "No documents yet", axe on the open dialog. Run — green.
- [ ] **Step 6: lint, typecheck, commit** "Delete a project document after confirming".

### Task 6: See how many documents each project has

**Files:**
- Modify: `frontend/src/api/projects.ts` (`Project` gets `documents?: Document[]`), `frontend/src/projects/ProjectsTable.tsx`, `frontend/src/projects/ProjectsTable.module.css`, `frontend/src/projects/ProjectsPage.test.tsx`, `frontend/e2e/projects.spec.ts`

- [ ] **Step 1: Failing test** — the list has a column header "Documents" and each row the count from `documents.length` ("3", "0"); a project without the field shows "0"; on the phone card the count reads "3 documents" / "1 document".
- [ ] **Step 2: Run** — fail. **Step 3: Implement** (right-aligned column, hidden header on cards like the others). **Step 4: Run** — green.
- [ ] **Step 5: e2e** — in the projects list test, a project with one document through `uploadViaApi` shows "1"; axe. Run — green.
- [ ] **Step 6: lint, typecheck, commit** "See how many documents each project has in the projects list".
