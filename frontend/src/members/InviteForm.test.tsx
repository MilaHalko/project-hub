import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Member } from "../api/members";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const PROJECT_ID = "10000000-0000-4000-8000-000000000001";
const MILA_ID = "00000000-0000-4000-8000-000000000001";

const project: Project = {
  id: PROJECT_ID,
  name: "Website redesign",
  description: "",
  owner: { id: MILA_ID, login: "mila" },
  my_role: "owner",
  created_at: "2026-11-12T10:00:00Z",
  updated_at: "2026-11-14T09:30:00Z",
};

const mila: Member = {
  id: MILA_ID,
  login: "mila",
  role: "owner",
  joined_at: "2026-11-12T10:00:00Z",
};

const sam: Member = {
  id: "00000000-0000-4000-8000-000000000002",
  login: "sam",
  role: "participant",
  joined_at: "2026-11-15T10:00:00Z",
};

const INFO = `GET /api/project/${PROJECT_ID}/info`;
const MEMBERS = `GET /api/project/${PROJECT_ID}/members`;

function inviteKey(login: string): string {
  return `POST /api/project/${PROJECT_ID}/invite?${new URLSearchParams({ user: login }).toString()}`;
}

function invitesSent(fetchMock: ReturnType<typeof mockApi>): number {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")
    .length;
}

async function openOwnerPage(routes: Parameters<typeof mockApi>[0] = {}) {
  const fetchMock = mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: { status: 200, body: [mila] },
    ...routes,
  });
  renderApp(`/projects/${PROJECT_ID}`);
  const field = await screen.findByRole("textbox", { name: "Invite by login" });
  return { fetchMock, field };
}

test("invites a login, adds it to the list, clears and keeps focus", async () => {
  const user = userEvent.setup();
  let invited = false;
  await openOwnerPage({
    [MEMBERS]: () => ({ status: 200, body: invited ? [mila, sam] : [mila] }),
    [inviteKey("sam")]: () => {
      invited = true;
      return { status: 201, body: sam };
    },
  });
  const field = screen.getByRole("textbox", { name: "Invite by login" });

  await user.type(field, "sam");
  await user.click(screen.getByRole("button", { name: "Invite" }));

  const panel = screen.getByRole("region", { name: /Members/ });
  expect(
    await within(panel).findByText("sam", { selector: "span" }),
  ).toBeInTheDocument();
  expect(field).toHaveValue("");
  expect(field).toHaveFocus();
  expect(
    await screen.findByText("sam added to the project"),
  ).toBeInTheDocument();
});

test("sends the login trimmed", async () => {
  const user = userEvent.setup();
  const { fetchMock, field } = await openOwnerPage({
    [inviteKey("sam")]: { status: 201, body: sam },
  });

  await user.type(field, "  sam ");
  await user.click(screen.getByRole("button", { name: "Invite" }));

  expect(
    await screen.findByText("sam added to the project"),
  ).toBeInTheDocument();
  expect(invitesSent(fetchMock)).toBe(1);
});

test.each([
  ["", "Enter a login."],
  ["   ", "Enter a login."],
  ["x".repeat(33), "Use 32 characters or fewer."],
])("checks the login %j before sending", async (typed, message) => {
  const user = userEvent.setup();
  const { fetchMock, field } = await openOwnerPage();

  if (typed) await user.type(field, typed);
  await user.click(screen.getByRole("button", { name: "Invite" }));

  expect(await screen.findByText(message)).toBeInTheDocument();
  expect(field).toHaveAttribute("aria-invalid", "true");
  expect(field).toHaveAccessibleDescription(message);
  expect(invitesSent(fetchMock)).toBe(0);
});

test("clears the check message while typing a valid login", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage();

  await user.click(screen.getByRole("button", { name: "Invite" }));
  expect(await screen.findByText("Enter a login.")).toBeInTheDocument();
  await user.type(field, "s");

  expect(screen.queryByText("Enter a login.")).not.toBeInTheDocument();
  expect(field).not.toHaveAttribute("aria-invalid");
});

test.each([
  [
    404,
    "User not found",
    "No user with that login. Logins are case-sensitive.",
  ],
  [
    409,
    "User is already a participant of this project",
    "sam is already a member.",
  ],
  [
    409,
    "You already own this project",
    "That's your login. You already own this project.",
  ],
  [409, "Something new", "Couldn't invite sam. Try again."],
  [
    403,
    "Only the project owner can invite users",
    "Only the owner can invite people.",
  ],
  [422, "Bad login", "Check the login and try again."],
  [500, undefined, "Couldn't invite sam. Try again."],
])(
  "shows %i %j under the field and keeps the login",
  async (status, detail, message) => {
    const user = userEvent.setup();
    const { field } = await openOwnerPage({
      [inviteKey("sam")]: {
        status,
        body: detail === undefined ? undefined : { detail },
      },
    });

    await user.type(field, "sam");
    await user.click(screen.getByRole("button", { name: "Invite" }));

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(field).toHaveValue("sam");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(message);
  },
);

test("shows the API's message for a 422 field error", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage({
    [inviteKey("sam")]: {
      status: 422,
      body: {
        detail: [
          {
            loc: ["query", "user"],
            msg: "String should have at most 32 characters",
            type: "string_too_long",
          },
        ],
      },
    },
  });

  await user.type(field, "sam");
  await user.click(screen.getByRole("button", { name: "Invite" }));

  expect(
    await screen.findByText("String should have at most 32 characters"),
  ).toBeInTheDocument();
});

test("leaves the page when the project is gone", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage({
    [inviteKey("sam")]: { status: 404, body: { detail: "Project not found" } },
  });

  await user.type(field, "sam");
  await user.click(screen.getByRole("button", { name: "Invite" }));

  expect(
    await screen.findByText("This project no longer exists."),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test("sends one request on a double submit", async () => {
  const user = userEvent.setup();
  let release: () => void = () => undefined;
  const { fetchMock, field } = await openOwnerPage({
    [inviteKey("sam")]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 201, body: sam });
        };
      }),
  });

  await user.type(field, "sam");
  await user.keyboard("{Enter}");
  await user.keyboard("{Enter}");
  release();

  expect(
    await screen.findByText("sam added to the project"),
  ).toBeInTheDocument();
  expect(invitesSent(fetchMock)).toBe(1);
});

test("shows the only-you hint to a lone owner", async () => {
  await openOwnerPage();

  expect(
    await screen.findByText("Only you so far. Invite people by their login."),
  ).toBeInTheDocument();
});

test("hides the hint once someone else is a member", async () => {
  mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: { status: 200, body: [mila, sam] },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const panel = await screen.findByRole("region", { name: /Members/ });
  expect(await within(panel).findAllByRole("listitem")).toHaveLength(2);
  expect(
    screen.queryByText("Only you so far. Invite people by their login."),
  ).not.toBeInTheDocument();
});

test("hides the invite form from a participant", async () => {
  mockApi({
    [INFO]: {
      status: 200,
      body: {
        ...project,
        owner: { id: sam.id, login: "sam" },
        my_role: "participant",
      },
    },
    [MEMBERS]: {
      status: 200,
      body: [
        { ...sam, role: "owner" },
        { ...mila, role: "participant" },
      ],
    },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const panel = await screen.findByRole("region", { name: /Members/ });
  expect(await within(panel).findAllByRole("listitem")).toHaveLength(2);
  expect(
    screen.queryByRole("textbox", { name: "Invite by login" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Invite" }),
  ).not.toBeInTheDocument();
});

test("sends one request on a fast double click", async () => {
  const user = userEvent.setup();
  const { fetchMock, field } = await openOwnerPage({
    [inviteKey("sam")]: { status: 201, body: sam },
  });
  await user.type(field, "sam");
  const invite = screen.getByRole("button", { name: "Invite" });

  fireEvent.click(invite);
  fireEvent.click(invite);

  expect(
    await screen.findByText("sam added to the project"),
  ).toBeInTheDocument();
  expect(invitesSent(fetchMock)).toBe(1);
});

test("moves the focus to the field when the invite fails", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage({
    [inviteKey("sam")]: { status: 404, body: { detail: "User not found" } },
  });

  await user.type(field, "sam");
  await user.click(screen.getByRole("button", { name: "Invite" }));

  expect(
    await screen.findByText(
      "No user with that login. Logins are case-sensitive.",
    ),
  ).toBeInTheDocument();
  expect(field).toHaveFocus();
});

test("moves the focus to the field when a check fails", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage();

  await user.click(screen.getByRole("button", { name: "Invite" }));

  expect(await screen.findByText("Enter a login.")).toBeInTheDocument();
  expect(field).toHaveFocus();
});
