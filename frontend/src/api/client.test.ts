import { expect, test } from "vitest";
import { setToken } from "../auth/tokenStore";
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
