import type { Page } from "@playwright/test";
import { createUser, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi } from "./projects";

async function fitsWidth(page: Page): Promise<boolean> {
  return page.evaluate<boolean>(
    "document.documentElement.scrollWidth <= window.innerWidth",
  );
}

test("opens a project from the list and shows its header and details", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  await createProjectViaApi(request, user, {
    name: "Website redesign",
    description: "Line one\nLine two",
  });
  await page.goto("/projects");

  await page.getByRole("link", { name: "Website redesign" }).click();

  await expect(
    page.getByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeFocused();
  await expect(page).toHaveTitle("Website redesign — Project Hub");
  const owner = page.getByText("Owner", { exact: true });
  await expect(owner).toHaveCount(3);
  await expect(owner.nth(0)).toBeVisible();
  await expect(owner.nth(1)).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: /Members/ })
      .getByRole("listitem")
      .filter({ hasText: user.login })
      .getByText("Owner", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Delete project" }),
  ).toBeVisible();
  await expect(
    page.locator("dd").getByText(`${user.login} (you)`),
  ).toBeVisible();
  await expect(page.getByText("just now")).toBeVisible();
  const description = page.getByText("Line one");
  await expect(description).toHaveText("Line one\nLine two");
  await expect(description).toHaveCSS("white-space", "pre-line");
  const box = await description.boundingBox();
  const fontSize = await page.evaluate<number>(
    "parseFloat(getComputedStyle([...document.querySelectorAll('p')].find((p) => p.textContent.startsWith('Line one'))).fontSize)",
  );
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(fontSize * 2);
  await expectAccessible(page);
});

test("wraps a 100-character name without sideways scroll", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  const name = "W".repeat(100);
  const { id } = await createProjectViaApi(request, user, { name });

  await page.goto(`/projects/${id}`);

  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  expect(await fitsWidth(page)).toBe(true);
  await expectAccessible(page);
});

test.describe("another user's project", () => {
  test.use({ expectedApiStatuses: [404] });

  test("shows Project not found and leads back to the list", async ({
    page,
    request,
  }) => {
    const owner = await createUser(request);
    const { id } = await createProjectViaApi(request, owner, {
      name: "Private plans",
    });
    await signIn(page, request);

    await page.goto(`/projects/${id}`);

    await expect(
      page.getByRole("heading", { level: 1, name: "Project not found" }),
    ).toBeVisible();
    await expect(page.getByText("Private plans")).toHaveCount(0);
    await expectAccessible(page);

    await page.getByRole("link", { name: "Back to projects" }).click();

    await expect(page).toHaveURL("/projects");
    await expect(
      page.getByRole("heading", { level: 1, name: "Your projects" }),
    ).toBeVisible();
  });
});
