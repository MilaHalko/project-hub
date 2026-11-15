import { randomInt, randomUUID } from "node:crypto";
import type { APIRequestContext, Page } from "@playwright/test";

export type TestUser = { login: string; password: string };

export async function createUser(
  request: APIRequestContext,
): Promise<TestUser> {
  const login = (
    "e2e" +
    Date.now().toString(36) +
    randomInt(2 ** 40).toString(36)
  ).slice(0, 32);
  const password = "pw-" + randomUUID();
  const response = await request.post("/api/auth", {
    data: { login, password, repeat_password: password },
  });
  if (response.status() !== 201) {
    throw new Error(`POST /api/auth answered ${String(response.status())}`);
  }
  return { login, password };
}

export async function apiToken(
  request: APIRequestContext,
  user: TestUser,
): Promise<string> {
  const response = await request.post("/api/login", { data: user });
  if (response.status() !== 200) {
    throw new Error(`POST /api/login answered ${String(response.status())}`);
  }
  const { access_token } = (await response.json()) as { access_token: string };
  return access_token;
}

export async function signIn(
  page: Page,
  request: APIRequestContext,
  user?: TestUser,
): Promise<TestUser> {
  const signedIn = user ?? (await createUser(request));
  const token = await apiToken(request, signedIn);
  await page.addInitScript((value) => {
    if (sessionStorage.getItem("project-hub.e2e-seeded") !== null) return;
    sessionStorage.setItem("project-hub.token", value);
    sessionStorage.setItem("project-hub.e2e-seeded", "1");
  }, token);
  return signedIn;
}
