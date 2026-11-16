import { apiFetch } from "./client";
export type ShareLink = { email: string; expires_at: string };

export function shareProject(
  projectId: string,
  email: string,
): Promise<ShareLink> {
  const query = new URLSearchParams({ with: email });
  return apiFetch<ShareLink>(
    `/project/${encodeURIComponent(projectId)}/share?${query.toString()}`,
  );
}
