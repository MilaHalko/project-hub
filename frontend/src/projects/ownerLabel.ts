import type { Project } from "../api/projects";

export function ownerLabel(project: Project): string {
  return project.my_role === "owner"
    ? `${project.owner.login} (you)`
    : project.owner.login;
}
