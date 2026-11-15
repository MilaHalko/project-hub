import { apiToken, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi } from "./projects";

test("deletes a project after typing its name", async ({ page, request }) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, {
    name: "Website redesign",
    description: "",
  });
  await page.goto(`/projects/${id}`);
  const opener = page.getByRole("button", { name: "Delete project" });
  const dialog = page.getByRole("alertdialog", {
    name: "Delete this project?",
  });

  await opener.click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();

  await opener.click();
  const confirm = dialog.getByRole("button", { name: "Delete project" });
  await expect(confirm).toBeDisabled();
  await expect(confirm).toHaveCSS("opacity", "0.5");
  await expectAccessible(page);

  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(`**/api/project/${id}`, async (route) => {
    if (route.request().method() === "DELETE") await held;
    await route.continue();
  });
  await dialog
    .getByRole("textbox", { name: "Type the project name to confirm" })
    .fill("Website redesign");
  await expect(confirm).toBeEnabled();
  await confirm.click();
  const cancel = dialog.getByRole("button", { name: "Cancel" });
  await expect(cancel).toBeDisabled();
  await expect(cancel).toHaveCSS("opacity", "0.5");
  release();

  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByText("Project deleted")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Website redesign" }),
  ).toHaveCount(0);

  const token = await apiToken(request, user);
  const response = await request.get(`/api/project/${id}/info`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.status()).toBe(404);
});
