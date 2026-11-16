import { randomUUID } from "node:crypto";
import type { APIRequestContext } from "@playwright/test";
import { apiToken, createUser, signIn } from "./auth";
import { expect, expectAccessible, test } from "./fixtures";
import { readJoinLink, shareViaApi } from "./mail";
import { createProjectViaApi } from "./projects";

test.use({ expectedApiStatuses: [404] });

async function webJoinUrl(
  request: APIRequestContext,
  link: string,
  baseURL: string | undefined,
): Promise<string> {
  const response = await request.get(link, {
    headers: { Accept: "text/html" },
    maxRedirects: 0,
  });
  expect(response.status()).toBe(303);
  const location = response.headers().location ?? "";
  expect(location).toMatch(
    new RegExp(`^${(baseURL ?? "").replaceAll(".", "\\.")}/join\\?token=`),
  );
  return location;
}

function address(): string {
  return `join-${randomUUID().slice(0, 8)}@example.com`;
}

test("joins from the email link after logging in", async ({
  page,
  request,
  baseURL,
}) => {
  const owner = await createUser(request);
  const joiner = await createUser(request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });
  const to = address();
  await shareViaApi(request, owner, id, to);
  const url = await webJoinUrl(
    request,
    await readJoinLink(request, to),
    baseURL,
  );

  await page.goto(url);
  await expect(page).toHaveURL(/\/login\?next=%2Fjoin$/);
  await expect(
    page.getByText("Log in or create an account to join the project."),
  ).toBeVisible();
  await expectAccessible(page);

  await page.getByLabel("Login", { exact: true }).fill(joiner.login);
  await page.getByLabel("Password", { exact: true }).fill(joiner.password);
  await page.getByRole("button", { name: "Log in" }).click();

  await expect(
    page.getByRole("heading", { level: 1, name: "Join a project" }),
  ).toBeVisible();
  await expect(
    page.getByText(`You are logged in as @${joiner.login}.`),
  ).toBeVisible();
  expect(page.url()).not.toContain("token");
  await expectAccessible(page);

  await page.getByRole("button", { name: "Join project" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      `You joined as @${joiner.login}. You are a participant now.`,
    ),
  ).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("link", { name: "Open project" }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${id}$`));
  await expect(
    page.getByRole("button", { name: "Leave project" }),
  ).toBeVisible();

  await page.goto(url);
  await page.getByRole("button", { name: "Join project" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "This link doesn't work" }),
  ).toBeVisible();
  await expectAccessible(page);
});

test("leaves the link for the recipient when the owner opens it", async ({
  page,
  request,
  baseURL,
}) => {
  const owner = await signIn(page, request);
  const recipient = await createUser(request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Website redesign",
  });
  const to = address();
  await shareViaApi(request, owner, id, to);
  const url = await webJoinUrl(
    request,
    await readJoinLink(request, to),
    baseURL,
  );

  await page.goto(url);
  await page.getByRole("button", { name: "Join project" }).click();
  await expect(
    page.getByText(
      `You already have access as @${owner.login}. The link was not used, so it still works for the person it was sent to.`,
    ),
  ).toBeVisible();
  await expectAccessible(page);

  const token = new URL(url).searchParams.get("token") ?? "";
  const response = await request.get(
    `/api/join?${new URLSearchParams({ token }).toString()}`,
    {
      headers: {
        Authorization: `Bearer ${await apiToken(request, recipient)}`,
      },
    },
  );
  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({
    login: recipient.login,
    already_member: false,
  });
});
