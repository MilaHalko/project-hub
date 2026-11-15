import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const token = { access_token: "t-new", token_type: "bearer", expires_in: 3600 };
const me = {
  id: "00000000-0000-4000-8000-000000000001",
  login: "mila",
  created_at: "2026-11-14T12:00:00Z",
};

test("an expired session leads to the login page and back again", async () => {
  const user = userEvent.setup();
  let meCalls = 0;
  const fetchMock = mockApi({
    "GET /api/users/me": () => {
      meCalls += 1;
      return meCalls === 1 ? { status: 401 } : { status: 200, body: me };
    },
    "POST /api/login": { status: 200, body: token },
  });
  renderApp("/no-such-page");

  expect(
    await screen.findByRole("heading", { level: 1, name: "Log in" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Your session expired. Log in again."),
  ).toHaveAttribute("role", "status");
  expect(
    screen.getByRole("heading", { level: 1, name: "Log in" }),
  ).toHaveAccessibleDescription("Your session expired. Log in again.");

  await user.type(screen.getByLabelText("Login"), "mila");
  await user.type(screen.getByLabelText("Password"), "secret-pw");
  await user.click(screen.getByRole("button", { name: "Log in" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeInTheDocument();
  const meRequests = fetchMock.mock.calls.filter(
    ([url]) => url === "/api/users/me",
  );
  expect(meRequests).toHaveLength(2);
});
