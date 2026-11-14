import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { AppProviders } from "../AppProviders";
import { setToken } from "../auth/tokenStore";
import { routes } from "../routes";

export function renderApp(
  path: string,
  { token = "test-token" }: { token?: string | null } = {},
) {
  if (token !== null) setToken(token);
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  );
}
