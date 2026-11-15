import type { ProjectInput } from "../api/projects";

export type ProjectErrors = { name?: string; description?: string };

export function characterCount(text: string): number {
  return Array.from(text).length;
}

export function checkProject({
  name,
  description,
}: ProjectInput): ProjectErrors {
  const errors: ProjectErrors = {};
  const trimmed = name.trim();
  if (trimmed === "") errors.name = "Enter a project name.";
  else if (characterCount(trimmed) > 100)
    errors.name = "Use 100 characters or fewer.";
  else if (/\p{Cc}/u.test(name)) {
    errors.name = "Remove tabs and line breaks from the name.";
  }
  if (characterCount(description) > 2000) {
    errors.description = "Use 2000 characters or fewer.";
  }
  return errors;
}
