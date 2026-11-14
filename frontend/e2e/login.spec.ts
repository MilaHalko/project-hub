import { createUser } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";

test.use({ expectedApiStatuses: [401] });

test("logs in from a guarded page and stays logged in after a reload", async ({
  page,
  request,
}) => {
  const user = await createUser(request);

  await page.goto("/projects-x");
  await expect(
    page.getByRole("heading", { level: 1, name: "Log in" }),
  ).toBeVisible();
  await expect(page).toHaveURL("/login?next=%2Fprojects-x");
  await expectAccessible(page);

  await page.getByLabel("Login", { exact: true }).fill(user.login);
  await page.getByLabel("Password", { exact: true }).fill("wrong-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByText("Wrong login or password. Try again."),
  ).toBeVisible();
  await expectAccessible(page);

  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeVisible();
  await expect(page).toHaveURL("/projects-x");

  await page.reload();
  await expect(
    page.getByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeVisible();
  const storage = await page.evaluate(() => ({
    sessionKeys: Object.keys(sessionStorage),
    token: sessionStorage.getItem("project-hub.token"),
    localKeys: Object.keys(localStorage),
  }));
  expect(storage.sessionKeys).toEqual(["project-hub.token"]);
  expect(storage.token).toBeTruthy();
  expect(storage.localKeys).toEqual([]);
});
