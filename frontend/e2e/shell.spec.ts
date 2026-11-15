import { signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";

test("shows the shell at /", async ({ page, request }, testInfo) => {
  await signIn(page, request);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your projects" }),
  ).toBeVisible();
  const projectsLink = page.getByRole("link", { name: "Projects" });
  const menuButton = page.getByRole("button", { name: "Menu" });
  if (testInfo.project.name === "phone") {
    await menuButton.click();
  }
  await expect(projectsLink).toBeVisible();
  await expectAccessible(page);
  if (testInfo.project.name === "phone") {
    await page.keyboard.press("Escape");
    await expect(projectsLink).toBeHidden();
    await expect(menuButton).toBeFocused();
  }
});

test("shows not found for an unknown path", async ({ page, request }) => {
  await signIn(page, request);
  await page.goto("/no-such-page");
  await expect(
    page.getByRole("heading", { name: "Page not found" }),
  ).toBeVisible();
  await expectAccessible(page);
  await page.getByRole("link", { name: "Go to projects" }).click();
  await expect(page).toHaveURL("/");
  await expect(
    page.getByRole("heading", { name: "Your projects" }),
  ).toBeFocused();
});

test("skip link moves focus to the content", async ({ page, request }) => {
  await signIn(page, request);
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
});
