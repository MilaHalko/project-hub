import type { Project } from "../api/projects";

const MB = 1_048_576;
const TENTH = 0.1 * MB;

function megabytes(bytes: number): string {
  const value = bytes / MB;
  const rounded = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
  return String(rounded);
}

export function formatMegabytes(bytes: number): string {
  if (bytes > 0 && bytes < TENTH) return "less than 0.1 MB";
  return `${megabytes(bytes)} MB`;
}

function usedAmount(used: number, limit: number): string {
  if (used > 0 && used < TENTH) return "Less than 0.1 MB";
  const amount = megabytes(used);
  if (used < limit && amount === megabytes(limit)) {
    return String(Math.floor((used / MB) * 10) / 10);
  }
  return amount;
}

export function usedText(used: number, limit: number): string {
  return `${usedAmount(used, limit)} of ${formatMegabytes(limit)} used`;
}

export type Space = { used: number; limit: number };

export function spaceOf(project: Project): Space | null {
  const used = project.storage_used_bytes;
  const limit = project.storage_limit_bytes;
  if (used === undefined || limit === undefined) return null;
  return { used, limit };
}

export function isFull(space: Space | null): boolean {
  return space !== null && space.used >= space.limit;
}
