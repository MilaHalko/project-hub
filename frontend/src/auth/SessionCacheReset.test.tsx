import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render } from "@testing-library/react";
import { expect, test } from "vitest";
import { clearToken, setToken } from "./tokenStore";
import { SessionCacheReset } from "./SessionCacheReset";

const me = {
  id: "00000000-0000-4000-8000-000000000001",
  login: "mila",
  created_at: "2026-11-14T12:00:00Z",
};

function renderReset() {
  const client = new QueryClient();
  client.setQueryData(["me"], me);
  render(
    <QueryClientProvider client={client}>
      <SessionCacheReset />
    </QueryClientProvider>,
  );
  return client;
}

test("drops the cached user when the session ends", () => {
  setToken("t-1");
  const client = renderReset();

  act(() => {
    clearToken("expired");
  });

  expect(client.getQueryData(["me"])).toBeUndefined();
});

test("keeps the cached data when a login starts the session", () => {
  const client = renderReset();

  act(() => {
    setToken("t-1");
  });

  expect(client.getQueryData(["me"])).toEqual(me);
});

test("keeps the cached data when the token is swapped", () => {
  setToken("t-1");
  const client = renderReset();

  act(() => {
    setToken("t-2");
  });

  expect(client.getQueryData(["me"])).toEqual(me);
});
