import { render } from "@testing-library/react";
import { createMemoryRouter, parsePath, RouterProvider } from "react-router";
import { AppProviders } from "../AppProviders";
import { setToken } from "../auth/tokenStore";
import { routes } from "../routes";

export function renderApp(
  path: string,
  {
    token = "test-token",
    state,
  }: { token?: string | null; state?: unknown } = {},
) {
  if (token !== null) setToken(token);
  const router = createMemoryRouter(routes, {
    initialEntries: [{ ...parsePath(path), state }],
  });
  return render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  );
}
