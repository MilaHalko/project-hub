import { apiFetch } from "./client";

export type ProjectRole = "owner" | "participant";

export type Project = {
  id: string;
  name: string;
  description: string;
  owner: { id: string; login: string };
  my_role: ProjectRole;
  created_at: string;
  updated_at: string;
};

export function listProjects({
  role,
  limit,
  offset,
}: {
  role?: ProjectRole;
  limit: number;
  offset: number;
}): Promise<Project[]> {
  const query = new URLSearchParams();
  if (role) query.set("role", role);
  query.set("limit", String(limit));
  query.set("offset", String(offset));
  return apiFetch<Project[]>(`/projects?${query.toString()}`);
}

export function getProject(id: string): Promise<Project> {
  return apiFetch<Project>(`/project/${encodeURIComponent(id)}/info`);
}

export type ProjectInput = { name: string; description: string };

export function createProject(body: ProjectInput): Promise<Project> {
  return apiFetch<Project>("/projects", { method: "POST", body });
}

export function updateProject(
  id: string,
  body: ProjectInput,
): Promise<Project> {
  return apiFetch<Project>(`/project/${encodeURIComponent(id)}/info`, {
    method: "PUT",
    body,
  });
}
