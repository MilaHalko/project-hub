import { signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";

test("logs out from the sidebar and stays logged out", async ({
  page,
  request,
}, testInfo) => {
  await signIn(page, request);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Projects" }),
  ).toBeVisible();

  if (testInfo.project.name === "phone") {
    await page.getByRole("button", { name: "Menu" }).click();
  }
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("button", { name: "Log out" })
    .click();

  await expect(
    page.getByRole("heading", { level: 1, name: "Log in" }),
  ).toBeVisible();
  await expect(page.getByText("You are logged out.")).toBeVisible();
  await expectAccessible(page);

  await page.reload();
  await expect(
    page.getByRole("heading", { level: 1, name: "Log in" }),
  ).toBeVisible();

  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Log in" }),
  ).toBeVisible();
});
