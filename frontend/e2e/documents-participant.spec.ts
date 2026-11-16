import { createUser, signIn } from "./auth";
import { DOCX, PDF, sampleDocx, samplePdf, uploadViaApi } from "./documents";
import { expect, test } from "./fixtures";
import { createProjectViaApi, inviteViaApi } from "./projects";

test("lets a participant upload to the owner's project", async ({
  page,
  request,
}) => {
  const owner = await createUser(request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Shared files",
  });
  await uploadViaApi(request, owner, id, {
    name: "Owner notes.pdf",
    mimeType: PDF,
    buffer: samplePdf,
  });
  const participant = await createUser(request);
  await inviteViaApi(request, owner, id, participant.login);
  await signIn(page, request, participant);
  await page.goto(`/projects/${id}`);

  await page.getByLabel("Choose files").setInputFiles({
    name: "My part.docx",
    mimeType: DOCX,
    buffer: sampleDocx,
  });

  await expect(page.getByText("File uploaded")).toBeVisible();
  const rows = page
    .getByRole("list", { name: /^Documents/ })
    .getByRole("listitem");
  await expect(rows.nth(0)).toContainText(
    `Added just now by ${participant.login}`,
  );
  await expect(rows.nth(1)).toContainText(`by ${owner.login}`);
});
