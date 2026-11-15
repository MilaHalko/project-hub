import { apiFetch } from "./client";
import type { ProjectRole } from "./projects";

export type Member = {
  id: string;
  login: string;
  role: ProjectRole;
  joined_at: string;
};

export function membersKey(projectId: string) {
  return ["members", projectId] as const;
}

function membersPath(projectId: string): string {
  return `/project/${encodeURIComponent(projectId)}`;
}

export function listMembers(projectId: string): Promise<Member[]> {
  return apiFetch<Member[]>(`${membersPath(projectId)}/members`);
}

export function inviteMember(
  projectId: string,
  login: string,
): Promise<Member> {
  const query = new URLSearchParams({ user: login });
  return apiFetch<Member>(
    `${membersPath(projectId)}/invite?${query.toString()}`,
    { method: "POST" },
  );
}

export function removeMember(projectId: string, userId: string): Promise<void> {
  return apiFetch<undefined>(
    `${membersPath(projectId)}/members/${encodeURIComponent(userId)}`,
    { method: "DELETE" },
  );
}
