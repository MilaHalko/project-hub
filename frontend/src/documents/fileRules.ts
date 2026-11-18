import { ApiError } from "../api/errors";
import { formatMegabytes, usedText } from "./space";

export type FileKind = "pdf" | "docx" | "jpg" | "png";

export const ACCEPTED_FILES = ".pdf,.docx,.jpg,.jpeg,.png";

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
  if (lowered.endsWith(".jpg") || lowered.endsWith(".jpeg")) return "jpg";
  if (lowered.endsWith(".png")) return "png";
  return null;
}

export const MAX_FILE_BYTES = 10 * MB;

export function checkFile(file: File): string | null {
  if (fileKind(file.name) === null) {
    return `${file.name}: only pdf, docx, jpg and png documents are allowed`;
  }
  if (file.size > MAX_FILE_BYTES) {
    return `${file.name}: file is larger than 10 MB`;
  }
  if (file.size === 0) return `${file.name}: file is empty`;
  return null;
}

const LIMIT_REACHED = "Project storage limit reached: ";
const LIMIT_NUMBERS =
  /^Project storage limit reached: (\d+) (MB|bytes) of (\d+) (MB|bytes) used, this upload needs (\d+) (MB|bytes)$/;

function bytesOf(amount: string | undefined, unit: string | undefined) {
  return Number(amount) * (unit === "MB" ? MB : 1);
}

function limitMessage(detail: string, name: string): string {
  const numbers = LIMIT_NUMBERS.exec(detail);
  const room = "Delete documents to make room.";
  if (numbers === null) return `${name}: not enough space. ${room}`;
  const [, used, usedUnit, limit, limitUnit, needed, neededUnit] = numbers;
  const space = usedText(bytesOf(used, usedUnit), bytesOf(limit, limitUnit));
  const file = formatMegabytes(bytesOf(needed, neededUnit));
  return `${name}: not enough space. ${space}, this file needs ${file}. ${room}`;
}

function limitDetail(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status !== 413) return null;
  const { detail } = error;
  return typeof detail === "string" && detail.startsWith(LIMIT_REACHED)
    ? detail
    : null;
}

export function uploadErrorMessage(error: unknown, name: string): string {
  const limit = limitDetail(error);
  if (limit !== null) return limitMessage(limit, name);
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
