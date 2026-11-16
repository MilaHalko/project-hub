# Image previews: jpg/png documents and the resize Lambda (epic 7b)

Status: decided by the builder on 2026-11-16. The handoff asks to settle where
the images come from with the owner (Mila) through the user, and to use the
recommended option if she agrees or does not answer. The user asked for the
work to run without further questions, so the recommended option is used and
the remaining calls are the builder's; each is marked as such.

## Intent

The spec marks an image-resize Lambda as optional; the owner wants it. Today
documents are only pdf and docx, so the app has no images. This epic lets a
project hold jpg and png documents, has a Lambda make a small preview of each
one in S3 (S3 → S3, no database), and lets the API hand that preview out with
the same access rules as the document itself. It shows the S3 + Lambda
pattern a second time without a database, so it runs in the always-up
persistent layer.

## Goals

1. Upload and replace accept `.jpg`, `.jpeg` and `.png`, checked by content
   (JPEG starts with `FF D8 FF`, PNG with the 8-byte PNG signature), exactly
   like pdf and docx today. A mislabelled file is refused with 422. The size
   and count limits and the 7a project limit apply unchanged. Stored content
   types: `image/jpeg`, `image/png`.
2. An S3 event for a new image document under `projects/<id>/documents/<hex>`
   starts the Lambda. It reads the object, makes a JPEG preview that fits in
   512 × 512 px (aspect ratio kept, never enlarged, EXIF orientation applied,
   transparency flattened onto white, quality 80), and writes it to
   `projects/<id>/previews/<hex>.jpg` with `Content-Type: image/jpeg`.
3. An S3 event for a removed document deletes its preview, so replacing or
   deleting a document and deleting a project leave no preview behind.
4. `GET /document/<id>/preview` returns the preview (`200 image/jpeg`) to
   anyone who may download the document. It answers `404 {"detail": "This
   document has no preview"}` for pdf and docx and `404 {"detail": "The
   preview is not ready yet. Try again in a few seconds."}` for an image whose
   preview does not exist yet (builder's call: 404 for both, so a client needs
   one branch; the text tells them apart).
5. Previews never count towards the 7a project limit (the 7a Lambda counts
   only `documents/`), and the 7a rule no longer fires for preview objects.

## Non-goals and anti-goals

- No preview in the web app in this epic. The F4 design rejected browser
  previews; showing them, and letting the web upload zone accept jpg/png, is
  a separate frontend task recorded in the roadmap's frontend requests.
- No database column for previews: the Lambda never writes to the database
  (that is the point of 7b), so the API asks S3 whether the preview exists.
- Anti-goal: a Lambda that triggers itself (writing a preview must never start
  another run), and a bad image that retries forever.
- Anti-goal: a decompression bomb taking the Lambda down. Pillow's
  `MAX_IMAGE_PIXELS` guard stays on; such a file just gets no preview.
- Profile pictures (the handoff's second option) need a users-avatar backend
  task that does not exist; not chosen.

## Approaches

1. **EventBridge rule → Lambda directly, in the persistent layer (chosen).**
   The bucket already sends events to EventBridge (7a). No database and no VPC
   are needed, so the function sits outside the VPC, reaches S3 over its
   public endpoint, and costs nothing while idle. EventBridge invokes it
   asynchronously: Lambda retries an invoke that raised, EventBridge retries a
   delivery that failed, and both send what still fails to an SQS dead-letter
   queue.
2. EventBridge → SQS → Lambda like 7a. Rejected: 7a needed the queue to cap
   database connections; 7b has no database, so the queue only adds parts.
3. Resize in the API on upload. Rejected: the epic is about S3 + Lambda, and
   resizing 10 MB images inside the request would slow uploads.

## Decisions (builder's calls)

- **Preview size and format**: 512 px longest side, JPEG quality 80.
- **Key layout**: `projects/<project_id>/previews/<hex>.jpg`, the same `<hex>`
  as the document's key, so the API finds the preview from the document row
  and the Lambda finds it from the deleted key, with no lookup table.
- **Event filter**: the 7b rule matches only `Object Created` / `Object
  Deleted` for keys `projects/*/documents/*` (EventBridge `wildcard`), so the
  Lambda's own writes to `previews/` never reach it. The 7a rule changes from
  prefix `projects/` to the same wildcard, so preview writes stop starting the
  7a Lambda (which ignored them anyway).
- **Which objects are images**: the Lambda reads the object and checks the
  same JPEG/PNG signatures as the API; anything else (pdf, docx) is skipped
  without an error.
- **Pixel guard**: the handler sets Pillow's `MAX_IMAGE_PIXELS` to 40 000 000 (the
  function has 512 MB and a PNG cannot be reduced while it is decoded); JPEGs
  are decoded at reduced size (`draft`) before the orientation is applied.
- **Errors**: a file Pillow cannot open, or one over `MAX_IMAGE_PIXELS`, is
  logged (`image preview skipped`, key, reason) and does not raise, so it is
  not retried. S3 errors raise, so Lambda's asynchronous invoke retries the
  event (`event_invoke_config`: up to 2 retries, so up to 3 invocations,
  within 1 hour) and then sends it to the function's DLQ
  `project-hub-image-preview-dlq`. The EventBridge target's retry policy (same
  limits, same DLQ) covers only a failed delivery to the function, not an
  error the function raised.
- **Object gone before the Lambda read it** (replaced or deleted within
  seconds): `NoSuchKey` on read is not an error; the delete event for that key
  removes any preview.
- **Packaging**: the 7a pattern: `scripts/build_image_preview_lambda.sh`
  builds `dist/image-preview-lambda.zip` (arm64, Python 3.13) with Pillow from
  `poetry.lock`; boto3 comes from the runtime. Pillow joins the dev
  dependencies only (the API does not import it). The smoke test runs the zip
  in `public.ecr.aws/lambda/python:3.13` with the existing `lambda_package`
  marker; the existing CI job `lambda` gains a build step and artifact for the
  second zip (its test step already runs the marker).
- **Terraform (persistent layer)**: function `project-hub-image-preview`
  (python3.13, arm64, 512 MB, 30 s), its role (S3 `GetObject` on
  `projects/*/documents/*`, `PutObject` and `DeleteObject` on
  `projects/*/previews/*`, logs to its own group), log group 14 days, rule and
  target with a retry policy and the SQS DLQ, and the permission for
  EventBridge to invoke it. Variable `image_preview_zip`, default
  `../../dist/image-preview-lambda.zip`. A `terraform test` asserts the role
  cannot write under `documents/` (a security property: the Lambda must not be
  able to change what the API stored).
- **API**: `GET /document/<id>/preview` uses the existing `AccessibleDocument`
  dependency; it reads `projects/<project_id>/previews/<hex>.jpg` through the
  storage layer and returns it with `Cache-Control: private, max-age=300`.
  The `FileStorage` protocol gains `get_if_exists(key) -> bytes | None`.
- **Database**: migration `0007` extends the `documents.content_type` check
  constraint with `image/jpeg` and `image/png` (ORM model too). The only
  schema change.

## Owner's apply steps

1. Build both zips: `scripts/build_storage_usage_lambda.sh` and
   `scripts/build_image_preview_lambda.sh`.
2. `terraform -chdir=infra/persistent apply` (adds the preview function, rule
   and DLQ; changes nothing for the running app).
3. Upload a png to a project, wait a few seconds, call
   `GET /document/<id>/preview`; the log group
   `/aws/lambda/project-hub-image-preview` shows `image preview stored`.

## Acceptance criteria

1. Given a valid jpg or png, when it is uploaded or used to replace a
   document, then it is stored with `image/jpeg` / `image/png`; given a file
   named `.png` whose content is not PNG, then 422. (API tests, both backends)
2. Given migration 0007, then the check constraint accepts the image types,
   and the downgrade restores the old list. (migration tests)
3. Given an `Object Created` event for a png/jpg document key, when the
   handler runs, then `projects/<id>/previews/<hex>.jpg` exists, is a JPEG,
   fits in 512 × 512, keeps the aspect ratio, is not enlarged, honours EXIF
   orientation, and flattens transparency onto white. (handler tests, moto)
4. Given a pdf/docx object, an unreadable image, a decompression bomb, a
   missing object, or a key outside `documents/`, then no preview is written
   and the handler does not raise. Given an S3 error on write, it raises.
   (handler tests)
5. Given an `Object Deleted` event for a document key, then its preview is
   removed, and a missing preview is not an error. (handler test)
6. Given a member, when they call `GET /document/<id>/preview` for an image
   with a preview, then `200 image/jpeg` with the bytes; before the preview
   exists, 404 "not ready"; for a pdf, 404 "no preview"; for an outsider, the
   same 404 as the download. (API tests, both backends)
7. Given the built zip, when it runs in the real Lambda image with a moto
   bucket, then a preview appears for an uploaded png. (`lambda_package`)
8. Given the Terraform, then fmt, validate, tflint, checkov and `terraform
   test` pass, and the test proves the role cannot write under `documents/`.
   (commands)

## Plan (vertical slices, one commit each)

1. **Upload jpg and png documents, checked by content** — `DocumentType`
   JPEG/PNG, `detect_type`, extension map (`.jpg`, `.jpeg`, `.png`),
   migration 0007 and the model, README; tests: validation, upload and replace
   API tests, migration tests. (criteria 1, 2)
2. **Make a preview of each image document in a Lambda** — module
   `src/project_hub/image_preview/handler.py` (stdlib, boto3, botocore,
   Pillow only), Pillow dev dependency; tests against moto with images built
   by Pillow in the test. (criteria 3, 4, 5)
3. **Download an image document's preview** — storage `get_if_exists`, the
   route, README; API tests. (criterion 6)
4. **Build the preview Lambda zip and run it in the Lambda runtime** — build
   script, smoke test (`lambda_package`), CI `lambda` job build and artifact
   steps. (criterion 7)
5. **Deliver image document events to the preview Lambda in AWS** —
   persistent Terraform, the 7a rule pattern change, `terraform test`,
   infra/README apply steps. (criterion 8)
6. **Mark epic 7b as done in the roadmap** — row 7b ✅, the deferred question
   "Which images exist for the resize Lambda" decided, and a frontend request
   row "Show image previews and accept jpg/png uploads" (proposed).
