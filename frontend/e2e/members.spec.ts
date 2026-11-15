import { createUser, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi, inviteViaApi } from "./projects";

test("shows the owner and an invited participant in the members panel", async ({
  page,
  request,
}) => {
  const owner = await signIn(page, request);
  const participant = await createUser(request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });
  await inviteViaApi(request, owner, id, participant.login);

  await page.goto(`/projects/${id}`);
  const panel = page.getByRole("region", { name: /Members/ });
  const rows = panel.getByRole("listitem");

  await expect(
    panel.getByRole("heading", { level: 2, name: "Members 2" }),
  ).toBeVisible();
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText(`${owner.login} (you)`);
  await expect(rows.nth(0)).toContainText("Owner");
  await expect(rows.nth(1)).toContainText(participant.login);
  await expect(rows.nth(1)).toContainText("Participant");
  await expectAccessible(page);
});

test("fits a 32-character login without scrolling sideways", async ({
  page,
  request,
}) => {
  const owner = await signIn(page, request);
  const participant = await createUser(request, { loginLength: 32 });
  expect(participant.login).toHaveLength(32);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });
  await inviteViaApi(request, owner, id, participant.login);

  await page.goto(`/projects/${id}`);
  const panel = page.getByRole("region", { name: /Members/ });
  await expect(panel.getByText(participant.login)).toBeVisible();

  const fits = await page.evaluate<boolean>(
    "document.documentElement.scrollWidth <= window.innerWidth",
  );
  expect(fits).toBe(true);
  const panelBox = await panel.boundingBox();
  const badgeBox = await panel
    .getByRole("listitem")
    .nth(1)
    .getByText("Participant")
    .boundingBox();
  expect(panelBox).not.toBeNull();
  expect(badgeBox).not.toBeNull();
  if (panelBox && badgeBox) {
    expect(badgeBox.x + badgeBox.width).toBeLessThanOrEqual(
      panelBox.x + panelBox.width,
    );
  }
});
