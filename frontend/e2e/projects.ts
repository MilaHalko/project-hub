import type { APIRequestContext } from "@playwright/test";
import { apiToken, type TestUser } from "./auth";

export async function createProjectViaApi(
  request: APIRequestContext,
  user: TestUser,
  body: { name: string; description?: string },
): Promise<{ id: string; name: string }> {
  const token = await apiToken(request, user);
  const response = await request.post("/api/projects", {
    data: body,
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status() !== 201) {
    throw new Error(`POST /api/projects answered ${String(response.status())}`);
  }
  const { id, name } = (await response.json()) as { id: string; name: string };
  return { id, name };
}

export async function inviteViaApi(
  request: APIRequestContext,
  owner: TestUser,
  projectId: string,
  login: string,
): Promise<void> {
  const token = await apiToken(request, owner);
  const response = await request.post(
    `/api/project/${projectId}/invite?${new URLSearchParams({ user: login }).toString()}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (response.status() !== 201) {
    throw new Error(
      `POST /api/project/${projectId}/invite answered ${String(response.status())}`,
    );
  }
}
