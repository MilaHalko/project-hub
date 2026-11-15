import { randomUUID } from "node:crypto";
import { apiToken, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";

test.use({ expectedApiStatuses: [400] });

test("changes the password and stays logged in", async ({ page, request }) => {
  const user = await signIn(page, request);
  const newPassword = "pw-" + randomUUID();
  await page.goto("/profile");
  await expect(
    page.getByRole("heading", { level: 1, name: user.login }),
  ).toBeVisible();

  await page.getByLabel("Current password").fill("pw-" + randomUUID());
  await page.getByLabel("New password", { exact: true }).fill(newPassword);
  await page.getByLabel("Repeat new password").fill(newPassword);
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(
    page.getByText("Current password is wrong. Try again."),
  ).toBeVisible();
  await expectAccessible(page);

  await page.getByLabel("Current password").fill(user.password);
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByText("Password changed")).toBeVisible();
  await expect(page.getByLabel("Current password")).toHaveValue("");
  await expectAccessible(page);

  await page.reload();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(
    page.getByRole("heading", { level: 1, name: user.login }),
  ).toBeVisible();

  await expect(apiToken(request, user)).rejects.toThrow("401");
  await expect(
    apiToken(request, { login: user.login, password: newPassword }),
  ).resolves.toEqual(expect.any(String));
});
