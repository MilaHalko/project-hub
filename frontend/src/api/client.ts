import { clearToken, getToken } from "../auth/tokenStore";
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

type ApiRequest = {
  method?: string;
  body?: unknown;
  endsSessionOn401?: boolean;
};

async function send(
  path: string,
  init: ApiRequest,
): Promise<{ status: number; response: Response }> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const isForm = init.body instanceof FormData;
  if (init.body !== undefined && !isForm) {
    headers["Content-Type"] = "application/json";
  }
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: init.method ?? "GET",
      headers,
      body:
        init.body === undefined
          ? undefined
          : isForm
            ? (init.body as FormData)
            : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, null);
  }
  if (
    response.status === 401 &&
    init.endsSessionOn401 !== false &&
    token !== null &&
    getToken() === token
  ) {
    clearToken("expired");
  }
  return { status: response.status, response };
}

async function readText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    throw new ApiError(0, null);
  }
}

function isSuccess(status: number): boolean {
  return status >= 200 && status < 300;
}

export async function apiFetch<T>(
  path: string,
  init: ApiRequest = {},
): Promise<T> {
  const { status, response } = await send(path, init);
  const body = parse(await readText(response));
  if (!isSuccess(status)) throw new ApiError(status, detailOf(body));
  return body as T;
}

export async function apiFetchBlob(path: string): Promise<Blob> {
  const { status, response } = await send(path, {});
  if (!isSuccess(status)) {
    throw new ApiError(status, detailOf(parse(await readText(response))));
  }
  try {
    return await response.blob();
  } catch {
    throw new ApiError(0, null);
  }
}
