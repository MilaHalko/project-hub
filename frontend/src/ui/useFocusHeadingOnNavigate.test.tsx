import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, Link, RouterProvider } from "react-router";
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
