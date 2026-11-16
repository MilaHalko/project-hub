import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const PROJECT_ID = "10000000-0000-4000-8000-000000000001";
const KEY = "project-hub.join-token";
const READY_TEXT =
  "You are logged in as @mila. Join with this account, or log out to use another one.";

const project: Project = {
  id: PROJECT_ID,
  name: "Website redesign",
  description: "New home page and order form.",
  owner: { id: "00000000-0000-4000-8000-000000000002", login: "sam" },
  my_role: "participant",
  created_at: "2026-11-12T10:00:00Z",
  updated_at: "2026-11-14T09:30:00Z",
};

function joinKey(token: string): string {
  return `GET /api/join?${new URLSearchParams({ token }).toString()}`;
}

function joinsSent(fetchMock: ReturnType<typeof mockApi>): number {
  return fetchMock.mock.calls.filter(
    ([input]) => typeof input === "string" && input.startsWith("/api/join?"),
  ).length;
}

async function openReady(path = "/join?token=abc") {
  renderApp(path);
  await screen.findByRole("heading", { level: 1, name: "Join a project" });
  return screen.getByRole("main");
}

test("moves the token out of the address and asks a signed-out user to log in", async () => {
  mockApi({});
  renderApp("/join?token=abc", { token: null });

  expect(
    await screen.findByRole("heading", { level: 1, name: "Log in" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Log in or create an account to join the project."),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Create one" })).toHaveAttribute(
    "href",
    "/register?next=%2Fjoin",
  );
  expect(sessionStorage.getItem(KEY)).toBe("abc");
});

test("shows who will join and waits for a click", async () => {
  const fetchMock = mockApi({});
  const main = await openReady();

  expect(await within(main).findByText(READY_TEXT)).toBeInTheDocument();
  expect(
    within(main).getByRole("button", { name: "Join project" }),
  ).toBeInTheDocument();
  expect(joinsSent(fetchMock)).toBe(0);
  expect(sessionStorage.getItem(KEY)).toBe("abc");
});

test("joins once and shows the project", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    [joinKey("abc")]: {
      status: 200,
      body: { login: "mila", already_member: false, project },
    },
  });
  const main = await openReady();
  const join = within(main).getByRole("button", { name: "Join project" });

  fireEvent.click(join);
  fireEvent.click(join);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("You joined as @mila. You are a participant now."),
  ).toBeInTheDocument();
  expect(screen.getByText("Participant")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open project" })).toHaveAttribute(
    "href",
    `/projects/${PROJECT_ID}`,
  );
  expect(joinsSent(fetchMock)).toBe(1);
  expect(sessionStorage.getItem(KEY)).toBeNull();

  await user.click(screen.getByRole("link", { name: "Open project" }));
  expect(
    await screen.findByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("button", { name: "Leave project" }),
  ).toBeInTheDocument();
});

test("says when you already have access", async () => {
  mockApi({
    [joinKey("abc")]: {
      status: 200,
      body: {
        login: "mila",
        already_member: true,
        project: { ...project, my_role: "owner" },
      },
    },
  });
  const user = userEvent.setup();
  const main = await openReady();

  await user.click(within(main).getByRole("button", { name: "Join project" }));

  expect(
    await screen.findByText(
      "You already have access as @mila. The link was not used, so it still works for the person it was sent to.",
    ),
  ).toBeInTheDocument();
  expect(screen.getByText("Owner")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open project" })).toBeVisible();
  expect(sessionStorage.getItem(KEY)).toBeNull();
});

test.each([
  [404, { detail: "Invite link is invalid or expired" }],
  [422, { detail: [] }],
])("explains a link that doesn't work (%i)", async (status, body) => {
  mockApi({ [joinKey("abc")]: { status, body } });
  const user = userEvent.setup();
  const main = await openReady();

  await user.click(within(main).getByRole("button", { name: "Join project" }));

  expect(
    await screen.findByRole("heading", {
      level: 1,
      name: "This link doesn't work",
    }),
  ).toHaveFocus();
  expect(
    screen.getByText(
      "It may have expired, been used already, or been replaced by a newer link. Ask the project owner to send a new one.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Go to your projects" }),
  ).toHaveAttribute("href", "/projects");
  expect(sessionStorage.getItem(KEY)).toBeNull();
});

test("keeps the link when joining fails", async () => {
  mockApi({
    [joinKey("abc")]: () => {
      throw new TypeError("Failed to fetch");
    },
  });
  const user = userEvent.setup();
  const main = await openReady();

  await user.click(within(main).getByRole("button", { name: "Join project" }));

  expect(
    await within(main).findByText("Couldn't join the project. Try again."),
  ).toHaveAttribute("role", "alert");
  expect(
    within(main).getByRole("button", { name: "Join project" }),
  ).toBeInTheDocument();
  expect(sessionStorage.getItem(KEY)).toBe("abc");
});

test("keeps the link when the session ends", async () => {
  mockApi({
    [joinKey("abc")]: { status: 401, body: { detail: "Not authenticated" } },
  });
  const user = userEvent.setup();
  const main = await openReady();

  await user.click(within(main).getByRole("button", { name: "Join project" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Log in" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Create one" })).toHaveAttribute(
    "href",
    "/register?next=%2Fjoin",
  );
  expect(sessionStorage.getItem(KEY)).toBe("abc");
});

test("encodes the token for the API", async () => {
  const token = "a+b/c=&d";
  const fetchMock = mockApi({
    "GET /api/join?token=a%2Bb%2Fc%3D%26d": {
      status: 200,
      body: { login: "mila", already_member: false, project },
    },
  });
  const user = userEvent.setup();
  const main = await openReady(
    `/join?${new URLSearchParams({ token }).toString()}`,
  );

  await user.click(within(main).getByRole("button", { name: "Join project" }));

  expect(
    await screen.findByText("You joined as @mila. You are a participant now."),
  ).toBeInTheDocument();
  expect(joinsSent(fetchMock)).toBe(1);
});

test("a newer link replaces the saved one", async () => {
  sessionStorage.setItem(KEY, "old");
  mockApi({
    [joinKey("new")]: {
      status: 200,
      body: { login: "mila", already_member: false, project },
    },
  });
  const user = userEvent.setup();
  const main = await openReady("/join?token=new");

  await user.click(within(main).getByRole("button", { name: "Join project" }));

  expect(
    await screen.findByText("You joined as @mila. You are a participant now."),
  ).toBeInTheDocument();
});

test("says when there is no link", async () => {
  mockApi({});
  renderApp("/join");

  expect(
    await screen.findByRole("heading", { level: 1, name: "No invite link" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Open the link from your email again."),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Go to your projects" }),
  ).toHaveAttribute("href", "/projects");
});

test("log out keeps the link for the next person", async () => {
  mockApi({ "POST /api/logout": { status: 204 } });
  const user = userEvent.setup();
  const main = await openReady();

  await user.click(within(main).getByRole("button", { name: "Log out" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Log in" }),
  ).toBeInTheDocument();
  expect(sessionStorage.getItem(KEY)).toBe("abc");
});
