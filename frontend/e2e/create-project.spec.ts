import { signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";

test("creates a project from the empty list and opens its page", async ({
  page,
  request,
}) => {
  await signIn(page, request);
  await page.goto("/projects");
  await expect(
    page.getByRole("heading", { name: "Create your first project" }),
  ).toBeVisible();
  const opener = page.getByRole("button", { name: "New project" });

  await opener.click();
  const dialog = page.getByRole("dialog", { name: "New project" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "Name" })).toBeFocused();
  await expectAccessible(page);

  await dialog.getByRole("button", { name: "Create project" }).focus();
  for (let press = 0; press < 6; press += 1) {
    await page.keyboard.press("Tab");
    expect(
      await page.evaluate<boolean>(
        "document.activeElement === document.body || document.querySelector('dialog').contains(document.activeElement)",
      ),
    ).toBe(true);
  }

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();

  await opener.click();
  await dialog.getByRole("button", { name: "Create project" }).click();
  await expect(dialog.getByText("Enter a project name.")).toBeVisible();
  await expectAccessible(page);

  await dialog.getByRole("textbox", { name: "Name" }).fill("Website redesign");
  await dialog
    .getByRole("textbox", { name: "Description (optional)" })
    .fill("New home page for a coffee shop");
  await dialog.getByRole("button", { name: "Create project" }).click();

  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeVisible();
  await expect(page.getByText("Project created")).toBeVisible();

  await page
    .getByRole("navigation", { name: "Breadcrumb" })
    .getByRole("link", { name: "Projects" })
    .click();
  await expect(
    page.getByRole("region", { name: "Projects" }).getByRole("link").first(),
  ).toHaveText("Website redesign");
});

test("keeps the dialog open on repeated Escape while the project is created", async ({
  page,
  request,
}) => {
  await signIn(page, request);
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/projects", async (route) => {
    if (route.request().method() === "POST") await held;
    await route.continue();
  });
  await page.goto("/projects");
  await page.getByRole("button", { name: "New project" }).click();
  const dialog = page.getByRole("dialog", { name: "New project" });
  await dialog.getByRole("textbox", { name: "Name" }).fill("Website redesign");
  const create = dialog.getByRole("button", { name: "Create project" });
  await create.click();
  await expect(create).toHaveAttribute("aria-busy", "true");

  for (let press = 0; press < 5; press += 1) {
    await page.keyboard.press("Escape");
    await expect(page.locator("dialog")).toHaveJSProperty("open", true);
    await expect(create).toBeFocused();
  }
  await expect(dialog).toBeVisible();

  release();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}$/);
  await expect(dialog).toBeHidden();
});
