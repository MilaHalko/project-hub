import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const token = { access_token: "t-new", token_type: "bearer", expires_in: 3600 };

test("asks for a login and returns to the page afterwards", async () => {
  const user = userEvent.setup();
  mockApi({ "POST /api/login": { status: 200, body: token } });
  renderApp("/no-such-page?x=1", { token: null });

  expect(
    await screen.findByRole("heading", { level: 1, name: "Log in" }),
  ).toBeInTheDocument();
  await user.type(screen.getByLabelText("Login"), "mila");
  await user.type(screen.getByLabelText("Password"), "secret-pw");
  await user.click(screen.getByRole("button", { name: "Log in" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeInTheDocument();
});

test("shows the page when there is a token", async () => {
  renderApp("/");

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});
