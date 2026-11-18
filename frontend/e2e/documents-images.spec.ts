import { signIn } from "./auth";
import { animationsDone, PNG, samplePng, uploadViaApi } from "./documents";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi } from "./projects";

test.use({ expectedApiStatuses: [404] });

test("uploads a png from the file picker and lists it", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, { name: "Images" });
  await page.goto(`/projects/${id}`);

  await page.getByLabel("Choose files").setInputFiles({
    name: "Mood board.png",
    mimeType: PNG,
    buffer: samplePng,
  });

  const documents = page.getByRole("list", { name: /^Documents/ });
  await expect(documents.getByRole("listitem")).toHaveText(/Mood board\.png/);
  await expect(documents.getByText("PNG", { exact: true })).toBeVisible();
  await expect(page.getByText("File uploaded")).toBeVisible();
  await animationsDone(page);
  await expectAccessible(page);
});

test("shows a thumbnail once the preview is ready", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, { name: "Previews" });
  await uploadViaApi(request, user, id, {
    name: "Mood board.png",
    mimeType: PNG,
    buffer: samplePng,
  });
  let requests = 0;
  await page.route("**/api/document/*/preview", async (route) => {
    requests += 1;
    if (requests < 2) {
      await route.fulfill({ status: 404, json: { detail: "not ready" } });
      return;
    }
    await route.fulfill({ status: 200, contentType: PNG, body: samplePng });
  });
  await page.goto(`/projects/${id}`);

  const documents = page.getByRole("list", { name: /^Documents/ });
  await expect(documents.getByText("PNG", { exact: true })).toBeVisible();
  const thumbnail = documents.getByRole("img", {
    name: "Preview of Mood board.png",
  });
  await expect(thumbnail).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate<number>(
        "document.querySelector('img[alt^=\"Preview of\"]').naturalWidth",
      ),
    )
    .toBeGreaterThan(0);
  await expectAccessible(page);
});
