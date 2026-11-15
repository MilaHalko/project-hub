import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi, type Mock } from "vitest";
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

const members: Member[] = [
  {
    id: MILA_ID,
    login: "mila",
    role: "owner",
    joined_at: "2026-11-12T10:00:00Z",
  },
  {
    id: SAM_ID,
    login: "sam",
    role: "participant",
    joined_at: "2026-11-13T10:00:00Z",
  },
];

afterEach(() => {
  vi.useRealTimers();
});

const INFO = `GET /api/project/${PROJECT_ID}/info`;
const MEMBERS = `GET /api/project/${PROJECT_ID}/members`;

function membersCalls(fetchMock: Mock<typeof fetch>): number {
  return fetchMock.mock.calls.filter(
    ([url]) => url === `/api/project/${PROJECT_ID}/members`,
  ).length;
}

function panel(): HTMLElement {
  return screen.getByRole("region", { name: /Members/ });
}

test("lists members owner first with badges, (you) and the count", async () => {
  mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: { status: 200, body: members },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const items = await within(
    await screen.findByRole("region", { name: /Members/ }),
  ).findAllByRole("listitem");
  expect(items).toHaveLength(2);
  const [owner, participant] = items as [HTMLElement, HTMLElement];
  expect(owner).toHaveTextContent("mila (you)");
  expect(within(owner).getByText("Owner")).toBeInTheDocument();
  expect(participant).toHaveTextContent("sam");
  expect(participant).not.toHaveTextContent("(you)");
  expect(within(participant).getByText("Participant")).toBeInTheDocument();
  expect(owner.querySelector("[data-avatar]")).not.toBeNull();
  expect(participant.querySelector("[data-avatar]")).not.toBeNull();
  expect(
    within(panel()).getByRole("heading", { level: 2, name: "Members 2" }),
  ).toBeInTheDocument();
});

test("shows skeleton rows while members load", async () => {
  mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: () => new Promise(() => undefined),
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const loading = await screen.findByRole("status", {
    name: "Loading members",
  });
  expect(loading).toHaveAttribute("aria-busy", "true");
  expect(
    screen.getByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeInTheDocument();
});

test("shows an error with Try again that repeats the request", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  let failing = true;
  const fetchMock = mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: () =>
      failing ? { status: 500 } : { status: 200, body: members },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
  await vi.advanceTimersByTimeAsync(2000);
  expect(screen.getByText("Couldn't load the members.")).toBeInTheDocument();
  const failedCalls = membersCalls(fetchMock);
  failing = false;
  await user.click(within(panel()).getByRole("button", { name: "Try again" }));

  expect(
    await within(panel()).findByText("sam", { exact: false }),
  ).toBeInTheDocument();
  expect(membersCalls(fetchMock)).toBe(failedCalls + 1);
});

test("keeps the page when members answer 404", async () => {
  mockApi({
    [INFO]: { status: 200, body: project },
    [MEMBERS]: { status: 404, body: { detail: "Project not found" } },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  expect(
    await screen.findByText("Couldn't load the members."),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Owner", { selector: "dt" })).toBeInTheDocument();
});
