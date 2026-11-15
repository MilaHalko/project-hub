import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createMemoryRouter,
  Link,
  Navigate,
  RouterProvider,
} from "react-router";
import { useState } from "react";
import { expect, test } from "vitest";
import { RouteRoot } from "./RouteRoot";

test("focuses a plain h1 that has no tabindex after navigating", async () => {
  const user = userEvent.setup();
  const router = createMemoryRouter(
    [
      {
        element: <RouteRoot />,
        children: [
          { path: "/", element: <Link to="/plain">Go</Link> },
          { path: "/plain", element: <h1>Plain page</h1> },
        ],
      },
    ],
    { initialEntries: ["/"] },
  );
  render(<RouterProvider router={router} />);

  await user.click(screen.getByRole("link", { name: "Go" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Plain page" }),
  ).toHaveFocus();
});

test("leaves the focus alone when the first page redirects", async () => {
  const router = createMemoryRouter(
    [
      {
        element: <RouteRoot />,
        children: [
          { path: "/", element: <Navigate to="/plain" replace /> },
          { path: "/plain", element: <h1>Plain page</h1> },
        ],
      },
    ],
    { initialEntries: ["/"] },
  );
  render(<RouterProvider router={router} />);

  await screen.findByRole("heading", { level: 1, name: "Plain page" });
  expect(document.body).toHaveFocus();
});

test("focuses the heading after a redirect from a page that had one", async () => {
  const user = userEvent.setup();
  function Start() {
    const [done, setDone] = useState(false);
    if (done) return <Navigate to="/plain" replace />;
    return (
      <>
        <h1>Start page</h1>
        <button
          type="button"
          onClick={() => {
            setDone(true);
          }}
        >
          Continue
        </button>
      </>
    );
  }
  const router = createMemoryRouter(
    [
      {
        element: <RouteRoot />,
        children: [
          { path: "/", element: <Start /> },
          { path: "/plain", element: <h1>Plain page</h1> },
        ],
      },
    ],
    { initialEntries: ["/"] },
  );
  render(<RouterProvider router={router} />);

  await user.click(screen.getByRole("button", { name: "Continue" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Plain page" }),
  ).toHaveFocus();
});
