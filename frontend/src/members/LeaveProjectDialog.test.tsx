import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Member } from "../api/members";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const PROJECT_ID = "10000000-0000-4000-8000-000000000002";
const MILA_ID = "00000000-0000-4000-8000-000000000001";
const SAM_ID = "00000000-0000-4000-8000-000000000002";

const shared: Project = {
  id: PROJECT_ID,
  name: "Thesis materials",
  description: "",
  owner: { id: SAM_ID, login: "sam" },
  my_role: "participant",
  created_at: "2026-10-28T08:00:00Z",
  updated_at: "2026-11-13T16:00:00Z",
};

const members: Member[] = [
  { id: SAM_ID, login: "sam", role: "owner", joined_at: shared.created_at },
  {
    id: MILA_ID,
    login: "mila",
    role: "participant",
    joined_at: "2026-11-01T08:00:00Z",
  },
];

const INFO = `GET /api/project/${PROJECT_ID}/info`;
const MEMBERS = `GET /api/project/${PROJECT_ID}/members`;
const LEAVE = `DELETE /api/project/${PROJECT_ID}/members/${MILA_ID}`;

function calls(fetchMock: ReturnType<typeof mockApi>, key: string): number {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      typeof url === "string" && `${init?.method ?? "GET"} ${url}` === key,
  ).length;
}

async function openLeaveDialog(routes: Parameters<typeof mockApi>[0] = {}) {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    [INFO]: { status: 200, body: shared },
    [MEMBERS]: { status: 200, body: members },
    ...routes,
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await user.click(
    await screen.findByRole("button", { name: "Leave project" }),
  );
  const dialog = screen.getByRole("alertdialog", {
    name: "Leave this project?",
  });
  return { user, fetchMock, dialog };
}

test("shows a participant's controls", async () => {
  mockApi({
    [INFO]: { status: 200, body: shared },
    [MEMBERS]: { status: 200, body: members },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  expect(
    await screen.findByRole("button", { name: "Leave project" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  expect(
    screen.getByText("Participant", { selector: "span" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Delete project" }),
  ).not.toBeInTheDocument();
  const panel = screen.getByRole("region", { name: /Members/ });
  expect(await within(panel).findAllByRole("listitem")).toHaveLength(2);
  expect(
    screen.queryByRole("textbox", { name: "Invite by login" }),
  ).not.toBeInTheDocument();
  expect(
    within(panel).queryByRole("button", { name: /^Remove/ }),
  ).not.toBeInTheDocument();
});

test("hides Leave project from the owner", async () => {
  mockApi({
    [INFO]: {
      status: 200,
      body: {
        ...shared,
        owner: { id: MILA_ID, login: "mila" },
        my_role: "owner",
      },
    },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  expect(
    await screen.findByRole("button", { name: "Delete project" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Leave project" }),
  ).not.toBeInTheDocument();
});

test("leaves after confirming", async () => {
  const { user, fetchMock, dialog } = await openLeaveDialog({
    [LEAVE]: { status: 204 },
  });

  expect(dialog).toHaveAccessibleDescription(
    "You lose access to Thesis materials and its documents. Only the owner can invite you back.",
  );
  const infoCalls = calls(fetchMock, INFO);
  await user.click(
    within(dialog).getByRole("button", { name: "Leave project" }),
  );

  expect(
    await screen.findByText("You left Thesis materials"),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
  expect(calls(fetchMock, LEAVE)).toBe(1);
  expect(calls(fetchMock, INFO)).toBe(infoCalls);
});

test.each([
  [404, { detail: "Project not found" }],
  [404, { detail: "Participant not found" }],
  [422, { detail: [{ loc: ["path", "user_id"], msg: "bad", type: "uuid" }] }],
])("goes to projects on %i %j", async (status, body) => {
  const { user, dialog } = await openLeaveDialog({
    [LEAVE]: { status, body },
  });

  await user.click(
    within(dialog).getByRole("button", { name: "Leave project" }),
  );

  expect(
    await screen.findByText("You no longer have access to this project."),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test.each([
  [409, "The owner can't leave the project."],
  [500, "Couldn't leave the project. Try again."],
])("shows %i in the dialog", async (status, message) => {
  const { user, dialog } = await openLeaveDialog({ [LEAVE]: { status } });

  await user.click(
    within(dialog).getByRole("button", { name: "Leave project" }),
  );

  expect(await within(dialog).findByRole("alert")).toHaveTextContent(message);
});

test("waits for the own id", async () => {
  const { user, fetchMock, dialog } = await openLeaveDialog({
    "GET /api/users/me": () => new Promise(() => undefined),
    [LEAVE]: { status: 204 },
  });
  const confirm = within(dialog).getByRole("button", {
    name: "Leave project",
  });

  expect(confirm).toHaveAttribute("aria-busy", "true");
  await user.click(confirm);

  expect(
    fetchMock.mock.calls.filter(([, init]) => init?.method === "DELETE"),
  ).toHaveLength(0);
});

test("sends one request on a fast double click", async () => {
  const { fetchMock, dialog } = await openLeaveDialog({
    [LEAVE]: { status: 204 },
  });
  const leave = within(dialog).getByRole("button", { name: "Leave project" });
  await within(dialog).findByRole("button", {
    name: "Leave project",
    busy: false,
  });

  fireEvent.click(leave);
  fireEvent.click(leave);

  expect(
    await screen.findByText("You left Thesis materials"),
  ).toBeInTheDocument();
  expect(calls(fetchMock, LEAVE)).toBe(1);
});
