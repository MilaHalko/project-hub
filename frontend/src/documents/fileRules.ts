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
