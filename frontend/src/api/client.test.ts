import { expect, test } from "vitest";
import {
  clearToken,
  getEndReason,
  getToken,
  setToken,
} from "../auth/tokenStore";
import { mockApi } from "../test/mockApi";
import { apiFetch } from "./client";
import { ApiError } from "./errors";

function headersOf(fetchMock: ReturnType<typeof mockApi>) {
  return new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
}

test("calls the API under /api", async () => {
  const fetchMock = mockApi({
    "GET /api/users/me": { status: 200, body: { login: "mila" } },
  });

  await expect(apiFetch("/users/me")).resolves.toEqual({ login: "mila" });
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test("sends the token as a Bearer header", async () => {
  setToken("t-1");
  const fetchMock = mockApi({ "GET /api/users/me": { status: 200, body: {} } });

  await apiFetch("/users/me");

  expect(headersOf(fetchMock).get("Authorization")).toBe("Bearer t-1");
});

test("sends no Authorization header without a token", async () => {
  const fetchMock = mockApi({ "GET /api/users/me": { status: 200, body: {} } });

  await apiFetch("/users/me");

  expect(headersOf(fetchMock).has("Authorization")).toBe(false);
});

test("sends a body as JSON", async () => {
  const fetchMock = mockApi({ "POST /api/login": { status: 200, body: {} } });

  await apiFetch("/login", {
    method: "POST",
    body: { login: "mila", password: "secret-pw" },
  });

  expect(headersOf(fetchMock).get("Content-Type")).toBe("application/json");
  expect(fetchMock.mock.calls[0]?.[1]?.body).toBe(
    JSON.stringify({ login: "mila", password: "secret-pw" }),
  );
});

test("resolves nothing for 204", async () => {
  mockApi({ "POST /api/logout": { status: 204 } });

  await expect(apiFetch("/logout", { method: "POST" })).resolves.toBe(
    undefined,
  );
});

test("rejects a non-2xx answer with its status and detail", async () => {
  mockApi({
    "POST /api/auth": {
      status: 409,
      body: { detail: "Login 'x' is already taken" },
    },
  });

  const error = await apiFetch("/auth", { method: "POST", body: {} }).catch(
    (caught: unknown) => caught,
  );

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({
    status: 409,
    detail: "Login 'x' is already taken",
  });
});

test("rejects a network failure with status 0", async () => {
  mockApi({
    "GET /api/users/me": () => {
      throw new TypeError("Failed to fetch");
    },
  });

  const error = await apiFetch("/users/me").catch((caught: unknown) => caught);

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ status: 0 });
});

test("a 401 for the current token ends the session as expired", async () => {
  setToken("t-1");
  mockApi({ "GET /api/users/me": { status: 401 } });

  await apiFetch("/users/me").catch(() => undefined);

  expect(getToken()).toBeNull();
  expect(getEndReason()).toBe("expired");
});

test("a 401 for an old token leaves the newer token alone", async () => {
  setToken("old");
  mockApi({
    "GET /api/users/me": () => {
      setToken("new");
      return { status: 401 };
    },
  });

  const error = await apiFetch("/users/me").catch((caught: unknown) => caught);

  expect(error).toMatchObject({ status: 401 });
  expect(getToken()).toBe("new");
  expect(getEndReason()).toBeNull();
});

test("a 401 without a token only rejects", async () => {
  clearToken("logout");
  mockApi({ "POST /api/login": { status: 401 } });

  const error = await apiFetch("/login", { method: "POST", body: {} }).catch(
    (caught: unknown) => caught,
  );

  expect(error).toMatchObject({ status: 401 });
  expect(getToken()).toBeNull();
  expect(getEndReason()).toBe("logout");
});

test("sends a form as it is, without a JSON content type", async () => {
  setToken("t-1");
  const fetchMock = mockApi({ "POST /api/upload": { status: 201, body: {} } });
  const form = new FormData();
  form.append("files", new File(["%PDF-"], "a.pdf"));

  await apiFetch("/upload", { method: "POST", body: form });

  expect(fetchMock.mock.calls[0]?.[1]?.body).toBe(form);
  const headers = headersOf(fetchMock);
  expect(headers.has("Content-Type")).toBe(false);
  expect(headers.get("Authorization")).toBe("Bearer t-1");
});
