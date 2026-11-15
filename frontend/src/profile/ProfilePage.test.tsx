import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

afterEach(() => {
  vi.useRealTimers();
});

test("shows a loading bar and no heading while the user loads", async () => {
  mockApi({ "GET /api/users/me": () => new Promise(() => undefined) });
  renderApp("/profile");

  expect(
    await screen.findByRole("progressbar", { name: "Loading" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
});

test("shows the login and the member since date", async () => {
  mockApi({});
  renderApp("/profile");

  expect(
    await screen.findByRole("heading", { level: 1, name: "mila" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Member since 14 Nov 2026")).toBeInTheDocument();
  expect(screen.getByText("PROFILE")).toBeInTheDocument();
});

test("marks Profile as the current page in the nav", async () => {
  mockApi({});
  renderApp("/profile");

  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { name: "Profile" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

test("offers Try again after a server error and then shows the user", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let calls = 0;
  mockApi({
    "GET /api/users/me": () => {
      calls += 1;
      return calls <= 2
        ? { status: 500 }
        : {
            status: 200,
            body: {
              id: "00000000-0000-4000-8000-000000000001",
              login: "mila",
              created_at: "2026-11-14T12:00:00Z",
            },
          };
    },
  });
  renderApp("/profile");

  await vi.advanceTimersByTimeAsync(1500);
  const main = await screen.findByRole("main");
  expect(await within(main).findByRole("alert")).toHaveTextContent(
    "Something went wrong. Try again.",
  );
  expect(
    screen.getByRole("heading", { level: 1, name: "Profile" }),
  ).toBeInTheDocument();
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  await user.click(screen.getByRole("button", { name: "Try again" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "mila" }),
  ).toBeInTheDocument();
});
