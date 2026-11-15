import { randomUUID } from "node:crypto";
import { createUser, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi } from "./projects";

test.use({ expectedApiStatuses: [404] });

test("invites a registered user by login", async ({ page, request }) => {
  const owner = await signIn(page, request);
  const invited = await createUser(request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });

  await page.goto(`/projects/${id}`);
  const panel = page.getByRole("region", { name: /Members/ });
  await expect(
    panel.getByText("Only you so far. Invite people by their login."),
  ).toBeVisible();
  const field = panel.getByRole("textbox", { name: "Invite by login" });
  await field.fill(invited.login);
  await panel.getByRole("button", { name: "Invite" }).click();

  const rows = panel.getByRole("listitem");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toContainText(invited.login);
  await expect(rows.nth(1)).toContainText("Participant");
  await expect(
    page.getByText(`${invited.login} added to the project`),
  ).toBeVisible();
  await expect(field).toHaveValue("");
  await expect(field).toBeFocused();
  await expectAccessible(page);
});

test("explains an unknown login", async ({ page, request }) => {
  const owner = await signIn(page, request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });
  const unknown = `nobody-${randomUUID().slice(0, 8)}`;

  await page.goto(`/projects/${id}`);
  const field = page.getByRole("textbox", { name: "Invite by login" });
  await field.fill(unknown);
  await page.getByRole("button", { name: "Invite" }).click();

  await expect(field).toHaveAccessibleDescription(
    "No user with that login. Logins are case-sensitive.",
  );
  await expect(field).toHaveValue(unknown);
  await expectAccessible(page);
});
