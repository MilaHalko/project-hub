import type { APIRequestContext, Page } from "@playwright/test";
import { createUser, signIn, type TestUser } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi, inviteViaApi } from "./projects";

async function sharedProject(
  page: Page,
  request: APIRequestContext,
): Promise<{ owner: TestUser; participant: TestUser; id: string }> {
  const owner = await createUser(request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Thesis materials",
  });
  const participant = await signIn(page, request);
  await inviteViaApi(request, owner, id, participant.login);
  return { owner, participant, id };
}

test("shows a shared project to the invited user without owner controls", async ({
  page,
  request,
}) => {
  const { owner, participant } = await sharedProject(page, request);

  await page.goto("/projects?role=participant");
  await page.getByRole("link", { name: "Thesis materials" }).click();

  await expect(
    page.getByRole("heading", { level: 1, name: "Thesis materials" }),
  ).toBeVisible();
  await expect(page.getByText("Participant").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Leave project" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Delete project" }),
  ).toHaveCount(0);
  const panel = page.getByRole("region", { name: /Members/ });
  const rows = panel.getByRole("listitem");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText(owner.login);
  await expect(rows.nth(1)).toContainText(`${participant.login} (you)`);
  await expect(
    page.getByRole("textbox", { name: "Invite by login" }),
  ).toHaveCount(0);
  await expect(panel.getByRole("button", { name: /^Remove/ })).toHaveCount(0);
  await expectAccessible(page);
});

test("leaves a project", async ({ page, request }) => {
  const { id } = await sharedProject(page, request);

  await page.goto(`/projects/${id}`);
  const opener = page.getByRole("button", { name: "Leave project" });
  const dialog = page.getByRole("alertdialog", {
    name: "Leave this project?",
  });

  await opener.click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();

  await opener.click();
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Leave project" }).click();

  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByText("You left Thesis materials")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Thesis materials" }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Shared with me" }).click();
  await expect(page.getByText("Nothing shared with you yet")).toBeVisible();
});
