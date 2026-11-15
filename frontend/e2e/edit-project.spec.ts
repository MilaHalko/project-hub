import { signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi } from "./projects";

test("edits a project's name and description from its page", async ({
  page,
  request,
}) => {
  const user = await signIn(page, request);
  const { id } = await createProjectViaApi(request, user, {
    name: "Website redesign",
    description: "Old text",
  });
  await page.goto(`/projects/${id}`);
  const opener = page.getByRole("button", { name: "Edit" });

  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Edit project" });
  await expect(dialog.getByRole("textbox", { name: "Name" })).toHaveValue(
    "Website redesign",
  );
  await expect(dialog.getByText("8 / 2000")).toBeVisible();
  await expectAccessible(page);

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();

  await opener.click();
  await dialog.getByRole("textbox", { name: "Name" }).fill("Site v2");
  await dialog
    .getByRole("textbox", { name: "Description (optional)" })
    .fill("Fresh text");
  await dialog.getByRole("button", { name: "Save changes" }).click();

  await expect(
    page.getByRole("heading", { level: 1, name: "Site v2" }),
  ).toBeVisible();
  await expect(page.getByText("Fresh text")).toBeVisible();
  await expect(page.getByText("Changes saved")).toBeVisible();
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();

  await page
    .getByRole("navigation", { name: "Breadcrumb" })
    .getByRole("link", { name: "Projects" })
    .click();
  await expect(
    page.getByRole("region", { name: "Projects" }).getByRole("link").first(),
  ).toHaveText("Site v2");
});
