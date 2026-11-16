import type { Page } from "@playwright/test";
import { signIn } from "./auth";
import {
  animationsDone,
  PDF,
  samplePdf,
  sampleDocx,
  DOCX,
  uploadViaApi,
} from "./documents";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi } from "./projects";

const MB = 1_048_576;

async function expectUsed(page: Page, used: string) {
  const amount = used.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const text = new RegExp(`^${amount} of \\d+ MB used$`);
  await expect(page.getByRole("meter", { name: "Space used" })).toHaveAttribute(
    "aria-valuetext",
    text,
  );
  await expect(page.getByText(text)).toBeVisible();
}

test("follows uploads, replacements and deletes with the used space", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, { name: "Space" });
  await page.goto(`/projects/${id}`);
  await expect(page.getByText("No documents yet")).toBeVisible();
  await expectUsed(page, "0");
  await expectAccessible(page);

  await page.getByLabel("Choose files").setInputFiles({
    name: "Client brief.pdf",
    mimeType: PDF,
    buffer: samplePdf,
  });
  await expect(page.getByText("File uploaded")).toBeVisible();
  await expectUsed(page, "Less than 0.1 MB");

  await page.getByLabel("Replace Client brief.pdf").setInputFiles({
    name: "Client brief v2.pdf",
    mimeType: PDF,
    buffer: Buffer.concat([
      samplePdf,
      Buffer.alloc(1.5 * MB - samplePdf.length),
    ]),
  });
  await expect(page.getByText("File replaced")).toBeVisible();
  await expectUsed(page, "1.5");
  await animationsDone(page);
  await expectAccessible(page);

  await page
    .getByRole("button", { name: "Delete Client brief v2.pdf" })
    .click();
  await page
    .getByRole("alertdialog", { name: "Delete this document?" })
    .getByRole("button", { name: "Delete document" })
    .click();
  await expect(page.getByText("No documents yet")).toBeVisible();
  await expectUsed(page, "0");
});

test.describe("a file that does not fit in the project", () => {
  test.use({ expectedApiStatuses: [413] });

  test("says why and uploads the rest of the batch", async ({
    page,
    request,
  }) => {
    const user = await signIn(page, request);
    const { id } = await createProjectViaApi(request, user, { name: "Full" });
    const stored = Buffer.concat([samplePdf, Buffer.alloc(2 * MB)]);
    await uploadViaApi(request, user, id, {
      name: "Scan.pdf",
      mimeType: PDF,
      buffer: stored,
    });
    await page.goto(`/projects/${id}`);
    await expect(page.getByText("2 of 3 MB used")).toBeVisible();

    await page.getByLabel("Choose files").setInputFiles([
      {
        name: "Report.pdf",
        mimeType: PDF,
        buffer: Buffer.concat([
          samplePdf,
          Buffer.alloc(1.5 * MB - samplePdf.length),
        ]),
      },
      { name: "Site map.docx", mimeType: DOCX, buffer: sampleDocx },
    ]);

    await expect(page.getByText("File uploaded")).toBeVisible();
    await expect(
      page
        .getByRole("list", { name: "Uploads" })
        .getByText(
          "Report.pdf: not enough space. 2 of 3 MB used, this file needs 1.5 MB. Delete documents to make room.",
        ),
    ).toBeVisible();
    const documents = page.getByRole("list", { name: /^Documents/ });
    await expect(documents.getByRole("listitem")).toHaveCount(2);
    await expect(documents).toContainText("Site map.docx");
    await expect(
      page.getByRole("meter", { name: "Space used" }),
    ).toHaveAttribute(
      "aria-valuenow",
      String(stored.length + sampleDocx.length),
    );
    await animationsDone(page);
    await expectAccessible(page);
  });
});
