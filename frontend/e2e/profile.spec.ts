import { apiToken, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";

test("shows the profile with the login and the member since date", async ({
  page,
  request,
}, testInfo) => {
  const user = await signIn(page, request);
  await page.goto("/");

  if (testInfo.project.name === "phone") {
    await page.getByRole("button", { name: "Menu" }).click();
  }
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Profile" })
    .click();

  await expect(
    page.getByRole("heading", { level: 1, name: user.login }),
  ).toBeVisible();
  const { created_at } = (await (
    await request.get("/api/users/me", {
      headers: { Authorization: `Bearer ${await apiToken(request, user)}` },
    })
  ).json()) as { created_at: string };
  const since = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(created_at));
  await expect(page.getByText(`Member since ${since}`)).toBeVisible();
  await expectAccessible(page);
});
