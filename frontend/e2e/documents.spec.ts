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
