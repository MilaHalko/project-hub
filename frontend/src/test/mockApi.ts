import { onTestFinished, vi, type Mock } from "vitest";

type Answer = { status: number; body?: unknown };
type Route = Answer | (() => Answer | Promise<Answer>);

const defaultRoutes: Record<string, Route> = {
  "GET /api/users/me": {
    status: 200,
    body: {
      id: "00000000-0000-4000-8000-000000000001",
      login: "mila",
      created_at: "2026-11-14T12:00:00Z",
    },
  },
};

export function mockApi(
  givenRoutes: Record<string, Route>,
): Mock<typeof fetch> {
  const routes = { ...defaultRoutes, ...givenRoutes };
  const unknown: string[] = [];
  onTestFinished(() => {
    if (unknown.length > 0) {
      throw new Error(
        `Requests without a mocked answer: ${unknown.join(", ")}`,
      );
    }
  });
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
    const key = `${init?.method ?? "GET"} ${url}`;
    const route = routes[key];
    if (route === undefined) {
      unknown.push(key);
      throw new Error(`No mocked answer for ${key}`);
    }
    const answer = typeof route === "function" ? await route() : route;
    const body = answer.body === undefined ? null : JSON.stringify(answer.body);
    return new Response(body, {
      status: answer.status,
      headers: body === null ? {} : { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
