import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Member } from "../api/members";
import type { Project } from "../api/projects";
import { formatDateTime } from "../projects/time";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const PROJECT_ID = "10000000-0000-4000-8000-000000000001";
const MILA_ID = "00000000-0000-4000-8000-000000000001";
const SAM_ID = "00000000-0000-4000-8000-000000000002";
const EXPIRES = "2026-11-23T14:05:00Z";
const HINT = "The link works once, for 7 days.";

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

const INFO = `GET /api/project/${PROJECT_ID}/info`;
const MEMBERS = `GET /api/project/${PROJECT_ID}/members`;

function shareKey(email: string): string {
  return `GET /api/project/${PROJECT_ID}/share?${new URLSearchParams({ with: email }).toString()}`;
}

function sharesSent(fetchMock: ReturnType<typeof mockApi>): number {
  return fetchMock.mock.calls.filter(
    ([input]) => typeof input === "string" && input.includes("/share?"),
  ).length;
}

async function openOwnerPage(routes: Parameters<typeof mockApi>[0] = {}) {
  const fetchMock = mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: { status: 200, body: [mila] },
    ...routes,
  });
  renderApp(`/projects/${PROJECT_ID}`);
  const field = await screen.findByRole("textbox", {
    name: "Send a link by email",
  });
  return { fetchMock, field };
}

function sendButton() {
  return screen.getByRole("button", { name: "Send link" });
}

test("sends a link, clears the field, keeps focus and says until when it works", async () => {
  const user = userEvent.setup();
  const { fetchMock, field } = await openOwnerPage({
    [shareKey("Anna@Example.com")]: {
      status: 200,
      body: { email: "anna@example.com", expires_at: EXPIRES },
    },
  });
  expect(field).toHaveAccessibleDescription(HINT);

  await user.type(field, " Anna@Example.com ");
  await user.click(sendButton());

  expect(
    await screen.findByText(
      `Link sent to anna@example.com. It works until ${formatDateTime(EXPIRES)}.`,
    ),
  ).toBeInTheDocument();
  expect(field).toHaveValue("");
  expect(field).toHaveFocus();
  expect(sharesSent(fetchMock)).toBe(1);
});

test("tells the owner to share again when the recipient must verify first", async () => {
  const user = userEvent.setup();
  const message =
    "No mail was sent yet. anna@example.com must first click the verification email from AWS. Then share again.";
  const { field } = await openOwnerPage({
    [shareKey("anna@example.com")]: {
      status: 200,
      body: { email: "anna@example.com", expires_at: EXPIRES, message },
    },
  });

  await user.type(field, "anna@example.com");
  await user.click(sendButton());

  expect(await screen.findByText(message)).toBeInTheDocument();
  expect(screen.queryByText(/^Link sent to/)).not.toBeInTheDocument();
});

test.each([
  ["", "Enter an email address."],
  ["   ", "Enter an email address."],
  ["anna", "Enter an address like name@example.com."],
  ["anna @example.com", "Enter an address like name@example.com."],
  [`${"a".repeat(243)}@example.com`, "Use 254 characters or fewer."],
])("checks the address %j before sending", async (typed, message) => {
  const user = userEvent.setup();
  const { fetchMock, field } = await openOwnerPage();

  if (typed) await user.type(field, typed);
  await user.click(sendButton());

  expect(await screen.findByText(message)).toBeInTheDocument();
  expect(field).toHaveAttribute("aria-invalid", "true");
  expect(field).toHaveAccessibleDescription(`${HINT} ${message}`);
  expect(field).toHaveFocus();
  expect(sharesSent(fetchMock)).toBe(0);
});

test("clears the check message while typing a valid address", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage();

  await user.click(sendButton());
  expect(
    await screen.findByText("Enter an email address."),
  ).toBeInTheDocument();
  await user.type(field, "anna@example.com");

  expect(screen.queryByText("Enter an email address.")).not.toBeInTheDocument();
  expect(field).not.toHaveAttribute("aria-invalid");
});

test.each([
  [422, undefined, "Check the email address and try again."],
  [
    429,
    "Too many pending share links for this project",
    "This project already has 10 unused links. Wait until one is used or expires, or invite by login.",
  ],
  [
    503,
    "Email sharing is not configured",
    "Email isn't set up on this server. Invite people by login instead.",
  ],
  [503, "Email could not be sent", "Couldn't send the email. Try again later."],
  [
    403,
    "Only the project owner can share the project",
    "Only the owner can share the project.",
  ],
  [500, undefined, "Couldn't send the link. Try again."],
])(
  "shows %i %j under the field and keeps the address",
  async (status, detail, message) => {
    const user = userEvent.setup();
    const { field } = await openOwnerPage({
      [shareKey("anna@example.com")]: {
        status,
        body: detail === undefined ? undefined : { detail },
      },
    });

    await user.type(field, "anna@example.com");
    await user.click(sendButton());

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(field).toHaveValue("anna@example.com");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(`${HINT} ${message}`);
    expect(field).toHaveFocus();
  },
);

test("says when the network is down", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage({
    [shareKey("anna@example.com")]: () => {
      throw new TypeError("Failed to fetch");
    },
  });

  await user.type(field, "anna@example.com");
  await user.click(sendButton());

  expect(
    await screen.findByText("Couldn't send the link. Try again."),
  ).toBeInTheDocument();
});

test("leaves the page when the project is gone", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage({
    [shareKey("anna@example.com")]: {
      status: 404,
      body: { detail: "Project not found" },
    },
  });

  await user.type(field, "anna@example.com");
  await user.click(sendButton());

  expect(
    await screen.findByText("This project no longer exists."),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test("sends one request on a fast double click", async () => {
  const user = userEvent.setup();
  const { fetchMock, field } = await openOwnerPage({
    [shareKey("anna@example.com")]: {
      status: 200,
      body: { email: "anna@example.com", expires_at: EXPIRES },
    },
  });
  await user.type(field, "anna@example.com");

  fireEvent.click(sendButton());
  fireEvent.click(sendButton());

  expect(await screen.findByText(/^Link sent to/)).toBeInTheDocument();
  expect(sharesSent(fetchMock)).toBe(1);
});

test("keeps the members list as it was", async () => {
  const user = userEvent.setup();
  const { field } = await openOwnerPage({
    [shareKey("anna@example.com")]: {
      status: 200,
      body: { email: "anna@example.com", expires_at: EXPIRES },
    },
  });

  await user.type(field, "anna@example.com");
  await user.click(sendButton());

  expect(await screen.findByText(/^Link sent to/)).toBeInTheDocument();
  const panel = screen.getByRole("region", { name: /Members/ });
  expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
});

test("hides the share form from a participant", async () => {
  mockApi({
    [INFO]: {
      status: 200,
      body: {
        ...project,
        owner: { id: SAM_ID, login: "sam" },
        my_role: "participant",
      },
    },
    [MEMBERS]: {
      status: 200,
      body: [
        { ...mila, id: SAM_ID, login: "sam" },
        { ...mila, role: "participant" },
      ],
    },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const panel = await screen.findByRole("region", { name: /Members/ });
  expect(await within(panel).findAllByRole("listitem")).toHaveLength(2);
  expect(
    screen.queryByRole("textbox", { name: "Send a link by email" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Send link" }),
  ).not.toBeInTheDocument();
});
