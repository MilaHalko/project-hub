import { apiToken, createUser, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";

test.use({ expectedApiStatuses: [401] });

test("sends the user to log in when the session was revoked", async ({
  page,
  request,
}) => {
  const user = await createUser(request);
  await signIn(page, request, user);
  await page.goto("/no-such-page");
  await expect(
    page.getByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeVisible();

  const token = await apiToken(request, user);
  const logout = await request.post("/api/logout", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(logout.status()).toBe(204);

  await page.reload();
  await expect(
    page.getByRole("heading", { level: 1, name: "Log in" }),
  ).toBeVisible();
  await expect(
    page.getByText("Your session expired. Log in again."),
  ).toBeVisible();
  await expectAccessible(page);

  await page.getByLabel("Login", { exact: true }).fill(user.login);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeVisible();
  await expect(page).toHaveURL("/no-such-page");
});
