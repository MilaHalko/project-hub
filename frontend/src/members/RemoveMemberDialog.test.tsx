import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Member } from "../api/members";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const PROJECT_ID = "10000000-0000-4000-8000-000000000001";
const MILA_ID = "00000000-0000-4000-8000-000000000001";
const SAM_ID = "00000000-0000-4000-8000-000000000002";

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
  id: SAM_ID,
  login: "sam",
  role: "participant",
  joined_at: "2026-11-13T10:00:00Z",
};

const INFO = `GET /api/project/${PROJECT_ID}/info`;
const MEMBERS = `GET /api/project/${PROJECT_ID}/members`;
const REMOVE_SAM = `DELETE /api/project/${PROJECT_ID}/members/${SAM_ID}`;

function deletesSent(fetchMock: ReturnType<typeof mockApi>): number {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === "DELETE")
    .length;
}

async function openRemoveDialog(routes: Parameters<typeof mockApi>[0] = {}) {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: { status: 200, body: [mila, sam] },
    ...routes,
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await user.click(await screen.findByRole("button", { name: "Remove sam" }));
  const dialog = screen.getByRole("alertdialog", { name: "Remove sam?" });
  return { user, fetchMock, dialog };
}

test("removes a participant after confirming", async () => {
  let removed = false;
  const { user, dialog } = await openRemoveDialog({
    [MEMBERS]: () => ({
      status: 200,
      body: removed ? [mila] : [mila, sam],
    }),
    [REMOVE_SAM]: () => {
      removed = true;
      return { status: 204 };
    },
  });

  expect(dialog).toHaveAccessibleDescription(
    "sam loses access to Website redesign and its documents. You can invite them again later.",
  );
  await user.click(within(dialog).getByRole("button", { name: "Remove" }));

  expect(
    await screen.findByText("sam removed from the project"),
  ).toBeInTheDocument();
  const panel = screen.getByRole("region", { name: /Members/ });
  expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
  expect(
    screen.queryByRole("alertdialog", { name: "Remove sam?" }),
  ).not.toBeInTheDocument();
  expect(
    within(panel).getByRole("heading", { level: 2, name: /Members/ }),
  ).toHaveFocus();
});

test("Cancel changes nothing", async () => {
  const { user, fetchMock, dialog } = await openRemoveDialog();

  await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

  expect(
    screen.queryByRole("alertdialog", { name: "Remove sam?" }),
  ).not.toBeInTheDocument();
  expect(deletesSent(fetchMock)).toBe(0);
  expect(
    screen.getByRole("button", { name: "Remove sam" }),
  ).toBeInTheDocument();
});

test("treats Participant not found as done", async () => {
  let gone = false;
  const { user, dialog } = await openRemoveDialog({
    [MEMBERS]: () => ({ status: 200, body: gone ? [mila] : [mila, sam] }),
    [REMOVE_SAM]: () => {
      gone = true;
      return { status: 404, body: { detail: "Participant not found" } };
    },
  });

  await user.click(within(dialog).getByRole("button", { name: "Remove" }));

  expect(
    await screen.findByText("sam is no longer a member."),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("alertdialog", { name: "Remove sam?" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Remove sam" }),
  ).not.toBeInTheDocument();
});

test.each([
  [404, { detail: "Project not found" }],
  [422, { detail: [{ loc: ["path", "user_id"], msg: "bad", type: "uuid" }] }],
])("leaves the page when the project is gone (%i)", async (status, body) => {
  const { user, dialog } = await openRemoveDialog({
    [REMOVE_SAM]: { status, body },
  });

  await user.click(within(dialog).getByRole("button", { name: "Remove" }));

  expect(
    await screen.findByText("This project no longer exists."),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test.each([
  [403, "You don't have permission to do this."],
  [500, "Couldn't remove sam. Try again."],
])("shows %i in the dialog", async (status, message) => {
  const { user, dialog } = await openRemoveDialog({
    [REMOVE_SAM]: { status },
  });

  await user.click(within(dialog).getByRole("button", { name: "Remove" }));

  expect(await within(dialog).findByRole("alert")).toHaveTextContent(message);
  expect(
    screen.getByRole("alertdialog", { name: "Remove sam?" }),
  ).toBeInTheDocument();
});

test("offers Remove only on participant rows", async () => {
  mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: { status: 200, body: [mila, sam] },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  expect(
    await screen.findByRole("button", { name: "Remove sam" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Remove mila" }),
  ).not.toBeInTheDocument();
});

test("hides Remove from a participant", async () => {
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
        { ...sam, role: "owner" },
        { ...mila, role: "participant" },
      ],
    },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const panel = await screen.findByRole("region", { name: /Members/ });
  expect(await within(panel).findAllByRole("listitem")).toHaveLength(2);
  expect(
    within(panel).queryByRole("button", { name: /^Remove/ }),
  ).not.toBeInTheDocument();
});

test("sends one request on a fast double click", async () => {
  const { fetchMock, dialog } = await openRemoveDialog({
    [REMOVE_SAM]: { status: 204 },
  });
  const remove = within(dialog).getByRole("button", { name: "Remove" });

  fireEvent.click(remove);
  fireEvent.click(remove);

  expect(
    await screen.findByText("sam removed from the project"),
  ).toBeInTheDocument();
  expect(deletesSent(fetchMock)).toBe(1);
});
