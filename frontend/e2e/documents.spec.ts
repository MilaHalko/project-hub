import { readFileSync } from "node:fs";
import { signIn } from "./auth";
import { DOCX, PDF, sampleDocx, samplePdf, uploadViaApi } from "./documents";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi } from "./projects";

test("lists uploaded documents with their sizes", async ({ page, request }) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, {
    name: "Website redesign",
  });
  await uploadViaApi(request, user, id, {
    name: "Client brief.pdf",
    mimeType: PDF,
    buffer: samplePdf,
  });
  await uploadViaApi(request, user, id, {
    name: "Site map.docx",
    mimeType: DOCX,
    buffer: sampleDocx,
  });

  await page.goto(`/projects/${id}`);

  const documents = page.getByRole("region", { name: /^Documents/ });
  await expect(documents.getByRole("heading", { level: 2 })).toHaveText(
    "Documents 2",
  );
  const rows = documents.getByRole("listitem");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("Site map.docx");
  await expect(rows.nth(0)).toContainText(`${String(sampleDocx.length)} B`);
  await expect(rows.nth(0)).toContainText(`Added just now by ${user.login}`);
  await expect(rows.nth(1)).toContainText("Client brief.pdf");
  await expect(rows.nth(1)).toContainText(`${String(samplePdf.length)} B`);
  await expectAccessible(page);
});

test("says when a project has no documents yet", async ({ page, request }) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, {
    name: "Empty project",
  });

  await page.goto(`/projects/${id}`);

  const documents = page.getByRole("region", { name: /^Documents/ });
  await expect(documents.getByText("No documents yet")).toBeVisible();
  await expect(
    documents.getByText("Upload the first one above."),
  ).toBeVisible();
  await expectAccessible(page);
});

test("uploads a pdf from the file picker", async ({ page, request }) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, { name: "Uploads" });
  await page.goto(`/projects/${id}`);

  await page.getByLabel("Choose files").setInputFiles({
    name: "Client brief.pdf",
    mimeType: PDF,
    buffer: samplePdf,
  });

  const documents = page.getByRole("list", { name: /^Documents/ });
  await expect(documents.getByRole("listitem")).toHaveText(/Client brief\.pdf/);
  await expect(page.getByText("File uploaded")).toBeVisible();
  await expectAccessible(page);
});

test("uploads a docx dropped on the zone", async ({ page, request }) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, { name: "Drops" });
  await page.goto(`/projects/${id}`);
  await expect(page.getByText("No documents yet")).toBeVisible();

  const dataTransfer = await page.evaluateHandle(
    `(() => {
      const bytes = Uint8Array.from(atob(${JSON.stringify(sampleDocx.toString("base64"))}), (c) => c.charCodeAt(0));
      const transfer = new DataTransfer();
      transfer.items.add(new File([bytes], "Site map.docx", { type: ${JSON.stringify(DOCX)} }));
      return transfer;
    })()`,
  );
  await page
    .getByText("Drop PDF or DOCX files here")
    .dispatchEvent("dragenter", { dataTransfer });
  const target = page.getByText("Drop to upload");
  await expect(target).toBeVisible();
  await expectAccessible(page);
  await target.dispatchEvent("dragover", { dataTransfer });
  await target.dispatchEvent("drop", { dataTransfer });

  const documents = page.getByRole("list", { name: /^Documents/ });
  await expect(documents.getByRole("listitem")).toHaveText(/Site map\.docx/);
  await expect(page.getByText("File uploaded")).toBeVisible();
});

test("uploads a 2 MB pdf through the web container", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, { name: "Big" });
  await page.goto(`/projects/${id}`);

  await page.getByLabel("Choose files").setInputFiles({
    name: "Scan.pdf",
    mimeType: PDF,
    buffer: Buffer.concat([samplePdf, Buffer.alloc(2 * 1024 * 1024)]),
  });

  const documents = page.getByRole("list", { name: /^Documents/ });
  await expect(documents.getByRole("listitem")).toContainText("2 MB");
  await expect(page.getByText("File uploaded")).toBeVisible();
});

test.describe("a file the API refuses", () => {
  test.use({ expectedApiStatuses: [422] });

  test("shows the API's message on the file", async ({ page, request }) => {
    const user = await signIn(page, request);
    const { id } = await createProjectViaApi(request, user, {
      name: "Refused",
    });
    await page.goto(`/projects/${id}`);

    await page.getByLabel("Choose files").setInputFiles({
      name: "fake.pdf",
      mimeType: PDF,
      buffer: Buffer.from("just text"),
    });

    const pending = page.getByRole("list", { name: "Uploads" });
    await expect(
      pending.getByText("fake.pdf: content is not a valid pdf"),
    ).toBeVisible();
    await expect(page.getByText("No documents yet")).toBeVisible();
    await expectAccessible(page);
    await pending.getByRole("button", { name: "Dismiss fake.pdf" }).click();
    await expect(pending).toHaveCount(0);
  });
});

test("downloads a document under its name", async ({ page, request }) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, {
    name: "Downloads",
  });
  await uploadViaApi(request, user, id, {
    name: "Client brief.pdf",
    mimeType: PDF,
    buffer: samplePdf,
  });
  await page.goto(`/projects/${id}`);

  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Client brief.pdf" }).click();
  const download = await downloading;

  expect(download.suggestedFilename()).toBe("Client brief.pdf");
  const path = await download.path();
  expect(readFileSync(path)).toEqual(samplePdf);
  await expectAccessible(page);
});

test("replaces a pdf with a docx and keeps its place", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, {
    name: "Versions",
  });
  await uploadViaApi(request, user, id, {
    name: "Client brief.pdf",
    mimeType: PDF,
    buffer: samplePdf,
  });
  await uploadViaApi(request, user, id, {
    name: "Site map.docx",
    mimeType: DOCX,
    buffer: sampleDocx,
  });
  await page.goto(`/projects/${id}`);

  const replace = page.getByLabel("Replace Client brief.pdf");
  await replace.focus();
  await replace.setInputFiles({
    name: "Client brief v2.docx",
    mimeType: DOCX,
    buffer: sampleDocx,
  });

  await expect(page.getByText("File replaced")).toBeVisible();
  const rows = page
    .getByRole("list", { name: /^Documents/ })
    .getByRole("listitem");
  await expect(rows.nth(0)).toContainText("Site map.docx");
  await expect(rows.nth(1)).toContainText("Client brief v2.docx");
  await expect(rows.nth(1)).toContainText(`Updated just now by ${user.login}`);
  await expect(page.getByLabel("Replace Client brief v2.docx")).toBeFocused();
  await expectAccessible(page);
});
