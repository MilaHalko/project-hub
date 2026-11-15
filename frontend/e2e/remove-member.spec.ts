import { apiToken, createUser, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi, inviteViaApi } from "./projects";

test("removes a participant after confirming", async ({ page, request }) => {
  const owner = await signIn(page, request);
  const participant = await createUser(request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });
  await inviteViaApi(request, owner, id, participant.login);

  await page.goto(`/projects/${id}`);
  const panel = page.getByRole("region", { name: /Members/ });
  const opener = panel.getByRole("button", {
    name: `Remove ${participant.login}`,
  });
  const dialog = page.getByRole("alertdialog", {
    name: `Remove ${participant.login}?`,
  });

  await opener.click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();

  await opener.click();
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Remove" }).click();

  await expect(dialog).toBeHidden();
  await expect(panel.getByRole("listitem")).toHaveCount(1);
  await expect(
    page.getByText(`${participant.login} removed from the project`),
  ).toBeVisible();
  await expect(
    panel.getByRole("heading", { level: 2, name: /Members/ }),
  ).toBeFocused();

  const token = await apiToken(request, participant);
  const response = await request.get(`/api/project/${id}/info`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.status()).toBe(404);
});
