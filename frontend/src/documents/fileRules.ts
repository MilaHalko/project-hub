import { ApiError } from "../api/errors";

export type FileKind = "pdf" | "docx";

const KB = 1024;
const MB = 1024 * KB;

function oneDecimal(value: number): string {
  return String(Math.round(value * 10) / 10);
}

export function formatSize(bytes: number): string {
  if (bytes < KB) return `${String(bytes)} B`;
  if (bytes < MB) return `${oneDecimal(bytes / KB)} KB`;
  return `${oneDecimal(bytes / MB)} MB`;
}

export function fileKind(name: string): FileKind | null {
  const lowered = name.toLowerCase();
  if (lowered.endsWith(".pdf")) return "pdf";
  if (lowered.endsWith(".docx")) return "docx";
  return null;
}

export const MAX_FILE_BYTES = 10 * MB;

export function checkFile(file: File): string | null {
  if (fileKind(file.name) === null) {
    return `${file.name}: only pdf and docx documents are allowed`;
  }
  if (file.size > MAX_FILE_BYTES) {
    return `${file.name}: file is larger than 10 MB`;
  }
  if (file.size === 0) return `${file.name}: file is empty`;
  return null;
}

export function uploadErrorMessage(error: unknown, name: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return `${name}: couldn't upload. Check your connection and try again.`;
    }
    if (error.status === 503) {
      return "File storage is unavailable. Try again later.";
    }
    if (typeof error.detail === "string") return error.detail;
  }
  return `${name}: couldn't upload. Try again.`;
}
