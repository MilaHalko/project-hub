import { getToken } from "../auth/tokenStore";
import { ApiError, type FieldError } from "./errors";

function parse(text: string): unknown {
  if (text === "") return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function detailOf(body: unknown): string | FieldError[] | null {
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return null;
  }
  const { detail } = body;
  if (typeof detail === "string" || Array.isArray(detail)) {
    return detail as string | FieldError[];
  }
  return null;
}

export async function apiFetch<T>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  let status: number;
  let text: string;
  try {
    const response = await fetch(`/api${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
    status = response.status;
    text = await response.text();
  } catch {
    throw new ApiError(0, null);
  }
  const body = parse(text);
  if (status < 200 || status >= 300) throw new ApiError(status, detailOf(body));
  return body as T;
}
