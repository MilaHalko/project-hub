import { screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

afterEach(() => {
  vi.useRealTimers();
});

test("shows the projects banner", async () => {
  mockApi({});
  renderApp("/");

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Sign-in and the projects list come next."),
  ).toBeInTheDocument();
});

test("greets the user by login", async () => {
  mockApi({});
  renderApp("/");

  expect(await screen.findByText("HI, MILA")).toBeInTheDocument();
});

test("shows PROJECT_HUB while the user loads", async () => {
  mockApi({ "GET /api/users/me": () => new Promise(() => undefined) });
  renderApp("/");

  expect(await screen.findByText("PROJECT_HUB")).toBeInTheDocument();
  expect(screen.queryByText(/^HI,/)).toBeNull();
});

test("keeps PROJECT_HUB when the user cannot be loaded", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockApi({ "GET /api/users/me": { status: 500 } });
  renderApp("/");

  await vi.advanceTimersByTimeAsync(2000);
  expect(screen.getByText("PROJECT_HUB")).toBeInTheDocument();
  expect(screen.queryByText(/something went wrong/i)).toBeNull();
});
