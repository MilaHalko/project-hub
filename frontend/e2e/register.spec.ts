import { randomInt } from "node:crypto";
import type { Page } from "@playwright/test";
import { createUser } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";

function uniqueLogin() {
  return (
    "reg" +
    Date.now().toString(36) +
    randomInt(2 ** 30).toString(36)
  ).slice(0, 32);
}

async function fillForm(
  page: Page,
  login: string,
  password: string,
  repeat: string,
) {
  await page.getByLabel("Login", { exact: true }).fill(login);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Repeat password", { exact: true }).fill(repeat);
  await page.getByRole("button", { name: "Create account" }).click();
}

test("shows a mismatch, then creates the account and lands on the projects page", async ({
  page,
}) => {
  const login = uniqueLogin();
  await page.goto("/register");
  await expect(
    page.getByRole("heading", { level: 1, name: "Create account" }),
  ).toBeVisible();
  await expectAccessible(page);

  await fillForm(page, login, "correct horse", "other horse");
  await expect(page.getByText("Passwords do not match")).toBeVisible();
  await expectAccessible(page);

  await fillForm(page, login, "correct horse", "correct horse");
  await expect(
    page.getByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeVisible();
  await expect(page.getByText(`HI, ${login.toUpperCase()}`)).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Account created");
});

test.describe("taken login", () => {
  test.use({ expectedApiStatuses: [409] });

  test("says the login is taken", async ({ page, request }) => {
    const user = await createUser(request);
    await page.goto("/register");
    await fillForm(page, user.login, user.password, user.password);
    await expect(
      page.getByText("That login is taken. Try another."),
    ).toBeVisible();
    await expectAccessible(page);
  });
});
