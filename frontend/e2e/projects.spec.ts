import type { Page } from "@playwright/test";
import { signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi } from "./projects";

function projectLinks(page: Page) {
  return page.getByRole("region", { name: "Projects" }).getByRole("link");
}

function tab(page: Page, name: string) {
  return page
    .getByRole("navigation", { name: "Filter projects" })
    .getByRole("link", { name });
}

test("lists the user's projects with the newest first", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  await createProjectViaApi(request, user, {
    name: "Thesis materials",
    description: "Chapter drafts, references and the reading list",
  });
  await createProjectViaApi(request, user, { name: "Website redesign" });

  await page.goto("/projects");

  await expect(projectLinks(page)).toHaveText([
    "Website redesign",
    "Thesis materials",
  ]);
  await expect(
    page.getByText("Chapter drafts, references and the reading list"),
  ).toBeVisible();
  await expect(page.getByText("No description")).toBeVisible();
  await expect(page.getByText(`${user.login} (you)`)).toHaveCount(2);
  await expect(tab(page, "All")).toHaveAttribute("aria-current", "page");
  await expectAccessible(page);
});

test("keeps the Owned tab in the address and after a reload", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  await createProjectViaApi(request, user, { name: "Thesis materials" });
  await createProjectViaApi(request, user, { name: "Website redesign" });
  await page.goto("/projects");
  await expect(projectLinks(page)).toHaveCount(2);

  await tab(page, "Owned").click();

  await expect(page).toHaveURL("/projects?role=owner");
  await expect(tab(page, "Owned")).toHaveAttribute("aria-current", "page");
  await expect(projectLinks(page)).toHaveText([
    "Website redesign",
    "Thesis materials",
  ]);
  await expectAccessible(page);

  await page.reload();

  await expect(tab(page, "Owned")).toHaveAttribute("aria-current", "page");
  await expect(projectLinks(page)).toHaveText([
    "Website redesign",
    "Thesis materials",
  ]);
});

test("explains an empty Shared with me tab", async ({ page, request }) => {
  const user = await signIn(page, request);
  await createProjectViaApi(request, user, { name: "Website redesign" });
  await page.goto("/projects");
  await expect(projectLinks(page)).toHaveCount(1);

  await tab(page, "Shared with me").click();

  await expect(page).toHaveURL("/projects?role=participant");
  await expect(
    page.getByRole("heading", { name: "Nothing shared with you yet" }),
  ).toBeVisible();
  await expect(projectLinks(page)).toHaveCount(0);
  await expectAccessible(page);
});

test("invites a new user to create the first project", async ({
  page,
  request,
}) => {
  await signIn(page, request);
  await page.goto("/");

  await expect(page).toHaveURL("/projects");
  await expect(
    page.getByRole("heading", { name: "Create your first project" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "New project" })).toHaveCount(
    1,
  );
  await expectAccessible(page);
});

test("wraps a long name without scrolling sideways", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  const name = "Long".padEnd(100, "x");
  await createProjectViaApi(request, user, { name });

  await page.goto("/projects");

  await expect(projectLinks(page)).toHaveText([name]);
  const fits = await page.evaluate<boolean>(
    "document.documentElement.scrollWidth <= window.innerWidth",
  );
  expect(fits).toBe(true);
  await expectAccessible(page);
});

test("loads the 21st project with Show more", async ({ page, request }) => {
  const user = await signIn(page, request);
  for (let number = 1; number <= 21; number += 1) {
    await createProjectViaApi(request, user, {
      name: `Project ${String(number)}`,
    });
  }

  await page.goto("/projects");

  await expect(projectLinks(page)).toHaveCount(20);
  await expectAccessible(page);

  await page.getByRole("button", { name: "Show more" }).click();

  await expect(projectLinks(page)).toHaveCount(21);
  await expect(page.getByRole("button", { name: "Show more" })).toHaveCount(0);
  await expectAccessible(page);
});
