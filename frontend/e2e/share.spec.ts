import { randomUUID } from "node:crypto";
import { signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { readJoinLink } from "./mail";
import { createProjectViaApi } from "./projects";

test.use({ expectedApiStatuses: [422] });

test("sends a join link by email", async ({ page, request }) => {
  const owner = await signIn(page, request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });
  const address = `share-${randomUUID().slice(0, 8)}@example.com`;

  await page.goto(`/projects/${id}`);
  const panel = page.getByRole("region", { name: /Members/ });
  const field = panel.getByRole("textbox", { name: "Send a link by email" });
  await field.fill(address);
  await panel.getByRole("button", { name: "Send link" }).click();

  await expect(page.getByText(`Link sent to ${address}.`)).toBeVisible();
  await expect(field).toHaveValue("");
  await expect(field).toBeFocused();
  expect(await readJoinLink(request, address)).toContain("/join?token=");
  await expectAccessible(page);
});

test("explains an address the server rejects", async ({ page, request }) => {
  const owner = await signIn(page, request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });

  await page.goto(`/projects/${id}`);
  const field = page.getByRole("textbox", { name: "Send a link by email" });
  await field.fill("anna@example");
  await page.getByRole("button", { name: "Send link" }).click();

  await expect(field).toHaveAccessibleDescription(
    "The link works once, for 7 days. Check the email address and try again.",
  );
  await expect(field).toHaveValue("anna@example");
  await expectAccessible(page);
});
