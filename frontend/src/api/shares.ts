import { apiFetch } from "./client";
import type { Project } from "./projects";

export type ShareLink = { email: string; expires_at: string };

export type JoinResult = {
  login: string;
  already_member: boolean;
  project: Project;
};

export function shareProject(
  projectId: string,
  email: string,
): Promise<ShareLink> {
  const query = new URLSearchParams({ with: email });
  return apiFetch<ShareLink>(
    `/project/${encodeURIComponent(projectId)}/share?${query.toString()}`,
  );
}

export function joinProject(token: string): Promise<JoinResult> {
  const query = new URLSearchParams({ token });
  return apiFetch<JoinResult>(`/join?${query.toString()}`);
}
