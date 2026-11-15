import { screen, waitFor } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { expect, test } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import { getToken } from "./tokenStore";

const token = { access_token: "t-new", token_type: "bearer", expires_in: 3600 };

async function openLogin(path = "/login") {
  renderApp(path, { token: null });
  await screen.findByRole("heading", { level: 1, name: "Log in" });
}

async function logIn(user: UserEvent) {
  await user.type(screen.getByLabelText("Login"), "mila");
  await user.type(screen.getByLabelText("Password"), "secret-pw");
  await user.click(screen.getByRole("button", { name: "Log in" }));
}

test("asks for both fields and sends nothing when they are empty", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({});
  await openLogin();

  await user.click(screen.getByRole("button", { name: "Log in" }));

  expect(screen.getByLabelText("Login")).toHaveAccessibleDescription(
    "Enter your login",
  );
  expect(screen.getByLabelText("Password")).toHaveAccessibleDescription(
    "Enter your password",
  );
  expect(screen.getByLabelText("Login")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(screen.getByLabelText("Login")).toHaveFocus();
  expect(fetchMock).not.toHaveBeenCalled();
});

test("sends the login and password", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    "POST /api/login": { status: 200, body: token },
  });
  await openLogin();

  await logIn(user);

  await screen.findByRole("heading", { level: 1, name: "Your projects" });
  expect(fetchMock.mock.calls[0]?.[1]?.body).toBe(
    JSON.stringify({ login: "mila", password: "secret-pw" }),
  );
});

test("says so when the login or password is wrong", async () => {
  const user = userEvent.setup();
  mockApi({
    "POST /api/login": {
      status: 401,
      body: { detail: "Invalid login or password" },
    },
  });
  await openLogin();

  await logIn(user);

  expect(
    await screen.findByText("Wrong login or password. Try again."),
  ).toHaveAttribute("role", "alert");
  expect(getToken()).toBeNull();
});

test("says something went wrong when the API is down and lets you retry", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    "POST /api/login": () => {
      throw new TypeError("Failed to fetch");
    },
  });
  await openLogin();

  await logIn(user);

  expect(
    await screen.findByText("Something went wrong. Try again."),
  ).toHaveAttribute("role", "alert");
  const button = screen.getByRole("button", { name: "Log in" });
  expect(button).not.toHaveAttribute("aria-busy");
  await user.click(button);
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

test("opens the page from next after logging in", async () => {
  const user = userEvent.setup();
  mockApi({ "POST /api/login": { status: 200, body: token } });
  await openLogin("/login?next=%2Fno-such-page");

  await logIn(user);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeInTheDocument();
  expect(getToken()).toBe("t-new");
});

test("ignores a next that leaves the app", async () => {
  const user = userEvent.setup();
  mockApi({ "POST /api/login": { status: 200, body: token } });
  await openLogin("/login?next=%2F%2Fevil.example");

  await logIn(user);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test("sends one request while the first is still running", async () => {
  const user = userEvent.setup();
  let answer!: (value: { status: number; body: unknown }) => void;
  const fetchMock = mockApi({
    "POST /api/login": () =>
      new Promise((resolve) => {
        answer = resolve;
      }),
  });
  await openLogin();

  await logIn(user);
  const button = screen.getByRole("button", { name: "Log in" });
  await waitFor(() => {
    expect(button).toHaveAttribute("aria-busy", "true");
  });
  await user.click(button);

  expect(fetchMock).toHaveBeenCalledTimes(1);
  answer({ status: 200, body: token });
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test("links to create an account and keeps next", async () => {
  await openLogin("/login?next=%2Fno-such-page");

  expect(screen.getByRole("link", { name: "Create one" })).toHaveAttribute(
    "href",
    "/register?next=%2Fno-such-page",
  );
});

test("goes to the projects page when already logged in", async () => {
  renderApp("/login");

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test("fills in the login of a freshly created account", async () => {
  renderApp("/login", {
    token: null,
    state: { reason: "created", login: "mila" },
  });

  expect(await screen.findByLabelText("Login")).toHaveValue("mila");
  expect(screen.getByText("Account created. Log in.")).toBeInTheDocument();
});
