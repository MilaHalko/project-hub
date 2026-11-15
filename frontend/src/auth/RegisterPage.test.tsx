import { screen, waitFor, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { expect, test } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import { getToken } from "./tokenStore";

const token = { access_token: "t-new", token_type: "bearer", expires_in: 3600 };
const created = {
  status: 201,
  body: { id: "u1", login: "mila", created_at: "2026-11-14T10:00:00Z" },
};
const me = { status: 200, body: created.body };

async function openRegister(path = "/register") {
  renderApp(path, { token: null });
  await screen.findByRole("heading", { level: 1, name: "Create account" });
}

async function fill(
  user: UserEvent,
  values: { login?: string; password?: string; repeat?: string } = {},
) {
  const { login = "mila", password = "secret-pw", repeat = password } = values;
  if (login) await user.type(screen.getByLabelText("Login"), login);
  if (password) {
    await user.type(
      screen.getByLabelText("Password", { exact: true }),
      password,
    );
  }
  if (repeat) {
    await user.type(screen.getByLabelText("Repeat password"), repeat);
  }
}

async function submit(user: UserEvent) {
  await user.click(screen.getByRole("button", { name: "Create account" }));
}

test("shows the fields with their hints", async () => {
  await openRegister();

  expect(screen.getByLabelText("Login")).toHaveAccessibleDescription(
    "3–32 characters: letters, digits, _ . -",
  );
  expect(
    screen.getByLabelText("Password", { exact: true }),
  ).toHaveAccessibleDescription("8–128 characters");
});

test.each([
  {
    name: "a login that is too short",
    values: { login: "ab" },
    field: "Login",
    message: "Use 3–32 characters: letters, digits, _ . -",
  },
  {
    name: "a login with a space",
    values: { login: "mi la" },
    field: "Login",
    message: "Use 3–32 characters: letters, digits, _ . -",
  },
  {
    name: "a short password",
    values: { password: "short" },
    field: "Password",
    message: "Use 8–128 characters",
  },
  {
    name: "a password that is not English",
    values: { password: "пароль123" },
    field: "Password",
    message: "Use only English letters, digits, keyboard symbols and spaces",
  },
  {
    name: "a password equal to the login",
    values: { login: "mila1234", password: "mila1234" },
    field: "Password",
    message: "Password must not equal the login",
  },
  {
    name: "a repeat that differs",
    values: { repeat: "other-pw" },
    field: "Repeat password",
    message: "Passwords do not match",
  },
])(
  "says so for $name and sends nothing",
  async ({ values, field, message }) => {
    const user = userEvent.setup();
    const fetchMock = mockApi({});
    await openRegister();

    await fill(user, values);
    await submit(user);

    const input = screen.getByLabelText(field, { exact: true });
    expect(input).toHaveAccessibleDescription(expect.stringContaining(message));
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  },
);

test("asks for empty fields", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({});
  await openRegister();

  await submit(user);

  expect(screen.getByLabelText("Login")).toHaveAccessibleDescription(
    expect.stringContaining("Use 3–32 characters: letters, digits, _ . -"),
  );
  expect(fetchMock).not.toHaveBeenCalled();
});

test("says the login is taken next to the Login field", async () => {
  const user = userEvent.setup();
  mockApi({
    "POST /api/auth": {
      status: 409,
      body: { detail: "Login 'mila' is already taken" },
    },
  });
  await openRegister();

  await fill(user);
  await submit(user);

  await waitFor(() => {
    expect(screen.getByLabelText("Login")).toHaveAccessibleDescription(
      expect.stringContaining("That login is taken. Try another."),
    );
  });
  expect(screen.getByLabelText("Login")).toHaveFocus();
  expect(getToken()).toBeNull();
});

test("shows an API validation message next to its field", async () => {
  const user = userEvent.setup();
  mockApi({
    "POST /api/auth": {
      status: 422,
      body: {
        detail: [
          { type: "value_error", loc: ["body", "login"], msg: "Bad login" },
        ],
      },
    },
  });
  await openRegister();

  await fill(user);
  await submit(user);

  await waitFor(() => {
    expect(screen.getByLabelText("Login")).toHaveAccessibleDescription(
      expect.stringContaining("Bad login"),
    );
  });
});

test("creates the account, logs in and lands on the projects page", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    "POST /api/auth": created,
    "POST /api/login": { status: 200, body: token },
    "GET /api/users/me": me,
  });
  await openRegister();

  await fill(user);
  await submit(user);

  await screen.findByRole("heading", { level: 1, name: "Your projects" });
  expect(
    fetchMock.mock.calls.slice(0, 2).map(([, init]) => init?.method),
  ).toEqual(["POST", "POST"]);
  expect(fetchMock.mock.calls.slice(0, 2).map(([url]) => url)).toEqual([
    "/api/auth",
    "/api/login",
  ]);
  expect(fetchMock.mock.calls[0]?.[1]?.body).toBe(
    JSON.stringify({
      login: "mila",
      password: "secret-pw",
      repeat_password: "secret-pw",
    }),
  );
  expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(
    JSON.stringify({ login: "mila", password: "secret-pw" }),
  );
  expect(
    within(screen.getByRole("status")).getByText("Account created"),
  ).toBeInTheDocument();
  expect(getToken()).toBe("t-new");
});

test("opens the page from next after creating the account", async () => {
  const user = userEvent.setup();
  mockApi({
    "POST /api/auth": created,
    "POST /api/login": { status: 200, body: token },
    "GET /api/users/me": me,
  });
  await openRegister("/register?next=%2Fno-such-page");

  await fill(user);
  await submit(user);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeInTheDocument();
});

test("goes to the login page with the login filled when logging in fails after the account is created", async () => {
  const user = userEvent.setup();
  mockApi({
    "POST /api/auth": created,
    "POST /api/login": { status: 500, body: { detail: "boom" } },
  });
  await openRegister();

  await fill(user);
  await submit(user);

  await screen.findByRole("heading", { level: 1, name: "Log in" });
  expect(screen.getByText("Account created. Log in.")).toHaveAttribute(
    "role",
    "status",
  );
  expect(screen.getByLabelText("Login")).toHaveValue("mila");
  expect(getToken()).toBeNull();
});

test("links to the login page and keeps next", async () => {
  await openRegister("/register?next=%2Fno-such-page");

  expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute(
    "href",
    "/login?next=%2Fno-such-page",
  );
});

test("says something went wrong when the API is down", async () => {
  const user = userEvent.setup();
  mockApi({
    "POST /api/auth": () => {
      throw new TypeError("Failed to fetch");
    },
  });
  await openRegister();

  await fill(user);
  await submit(user);

  expect(
    await screen.findByText("Something went wrong. Try again."),
  ).toHaveAttribute("role", "alert");
});

test("goes to the projects page when already logged in", async () => {
  renderApp("/register");

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});
