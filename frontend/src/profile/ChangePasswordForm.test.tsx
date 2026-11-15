import { screen, waitFor } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { expect, test } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import { getToken } from "../auth/tokenStore";

const token = { access_token: "t-new", token_type: "bearer", expires_in: 3600 };
const PUT = "PUT /api/users/me/password";

async function openProfile() {
  renderApp("/profile");
  await screen.findByRole("heading", { level: 1, name: "mila" });
}

async function fill(
  user: UserEvent,
  values: { current?: string; next?: string; repeat?: string } = {},
) {
  const { current = "old-secret", next = "new-secret", repeat = next } = values;
  if (current) {
    await user.type(screen.getByLabelText("Current password"), current);
  }
  if (next) {
    await user.type(screen.getByLabelText("New password"), next);
  }
  if (repeat) {
    await user.type(screen.getByLabelText("Repeat new password"), repeat);
  }
}

async function submit(user: UserEvent) {
  await user.click(screen.getByRole("button", { name: "Change password" }));
}

test("shows the panel with its line and hint", async () => {
  mockApi({});
  await openProfile();

  expect(
    screen.getByRole("heading", { level: 2, name: "Change password" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Changing the password logs you out on other devices."),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("New password")).toHaveAccessibleDescription(
    "8–128 characters",
  );
});

test.each([
  {
    name: "an empty current password",
    values: { current: "" },
    field: "Current password",
    message: "Enter your current password",
  },
  {
    name: "a short new password",
    values: { next: "short" },
    field: "New password",
    message: "Use 8–128 characters",
  },
  {
    name: "a repeat that differs",
    values: { repeat: "other-pw1" },
    field: "Repeat new password",
    message: "Passwords do not match",
  },
  {
    name: "a new password equal to the current one",
    values: { current: "same-secret", next: "same-secret" },
    field: "New password",
    message: "New password must differ from the current one",
  },
])(
  "says so for $name and sends nothing",
  async ({ values, field, message }) => {
    const user = userEvent.setup();
    const fetchMock = mockApi({});
    await openProfile();
    fetchMock.mockClear();

    await fill(user, values);
    await submit(user);

    const input = screen.getByLabelText(field, { exact: true });
    expect(input).toHaveAccessibleDescription(expect.stringContaining(message));
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  },
);

test("says the new password must not equal the login", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    "GET /api/users/me": {
      status: 200,
      body: {
        id: "u1",
        login: "milahalko",
        created_at: "2026-11-14T12:00:00Z",
      },
    },
  });
  renderApp("/profile");
  await screen.findByRole("heading", { level: 1, name: "milahalko" });
  fetchMock.mockClear();

  await fill(user, { next: "milahalko" });
  await submit(user);

  expect(screen.getByLabelText("New password")).toHaveAccessibleDescription(
    expect.stringContaining("Password must not equal the login"),
  );
  expect(fetchMock).not.toHaveBeenCalled();
});

test("says the current password is wrong next to its field", async () => {
  const user = userEvent.setup();
  mockApi({
    [PUT]: { status: 400, body: { detail: "Current password is incorrect" } },
  });
  await openProfile();

  await fill(user);
  await submit(user);

  const input = await screen.findByLabelText("Current password");
  await waitFor(() => {
    expect(input).toHaveAccessibleDescription(
      "Current password is wrong. Try again.",
    );
  });
  expect(input).toHaveFocus();
  expect(getToken()).toBe("test-token");
});

test("shows a server message about the new password in the form alert", async () => {
  const user = userEvent.setup();
  mockApi({
    [PUT]: {
      status: 422,
      body: { detail: "Password must not equal the login" },
    },
  });
  await openProfile();

  await fill(user);
  await submit(user);

  expect(
    await screen.findByText("Password must not equal the login"),
  ).toHaveAttribute("role", "alert");
});

test("shows a field message from a 422 list next to New password", async () => {
  const user = userEvent.setup();
  mockApi({
    [PUT]: {
      status: 422,
      body: {
        detail: [
          {
            type: "string_too_short",
            loc: ["body", "new_password"],
            msg: "String should have at least 8 characters",
          },
        ],
      },
    },
  });
  await openProfile();

  await fill(user);
  await submit(user);

  const input = screen.getByLabelText("New password");
  await waitFor(() => {
    expect(input).toHaveAccessibleDescription(
      expect.stringContaining("String should have at least 8 characters"),
    );
  });
  expect(input).toHaveFocus();
});

test("stores the new token, empties the fields and says so", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({ [PUT]: { status: 200, body: token } });
  await openProfile();

  await fill(user);
  await submit(user);

  expect(await screen.findByText("Password changed")).toBeInTheDocument();
  expect(getToken()).toBe("t-new");
  expect(screen.getByLabelText("Current password")).toHaveValue("");
  expect(screen.getByLabelText("New password")).toHaveValue("");
  expect(screen.getByLabelText("Repeat new password")).toHaveValue("");
  expect(
    screen.getByRole("heading", { level: 1, name: "mila" }),
  ).toBeInTheDocument();
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(call?.[1]?.body as string)).toEqual({
    current_password: "old-secret",
    new_password: "new-secret",
    repeat_new_password: "new-secret",
  });
});

test("says something went wrong when the network is down", async () => {
  const user = userEvent.setup();
  mockApi({
    [PUT]: () => {
      throw new TypeError("Failed to fetch");
    },
  });
  await openProfile();

  await fill(user);
  await submit(user);

  expect(
    await screen.findByText("Something went wrong. Try again."),
  ).toHaveAttribute("role", "alert");
  expect(getToken()).toBe("test-token");
});
