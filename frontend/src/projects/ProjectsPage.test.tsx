import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

afterEach(() => {
  vi.useRealTimers();
});

const ALL = "GET /api/projects?limit=21&offset=0";
const OWNED = "GET /api/projects?role=owner&limit=21&offset=0";
const SHARED = "GET /api/projects?role=participant&limit=21&offset=0";

const owned: Project = {
  id: "10000000-0000-4000-8000-000000000001",
  name: "Website redesign",
  description: "New home page, catalogue and order form for a coffee shop",
  owner: { id: "00000000-0000-4000-8000-000000000001", login: "mila" },
  my_role: "owner",
  created_at: "2026-11-12T10:00:00Z",
  updated_at: "2026-11-14T09:30:00Z",
};

const shared: Project = {
  id: "10000000-0000-4000-8000-000000000002",
  name: "Thesis materials",
  description: "",
  owner: { id: "00000000-0000-4000-8000-000000000002", login: "sam" },
  my_role: "participant",
  created_at: "2026-10-28T08:00:00Z",
  updated_at: "2026-11-13T16:00:00Z",
};

function requested(fetchMock: ReturnType<typeof mockApi>, url: string) {
  return fetchMock.mock.calls.filter(
    ([input, init]) => input === url && (init?.method ?? "GET") === "GET",
  ).length;
}

function tabs() {
  return within(screen.getByRole("navigation", { name: "Filter projects" }));
}

test("opens the projects list from /", async () => {
  const fetchMock = mockApi({});
  renderApp("/");

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Projects you own and projects you were invited to."),
  ).toBeInTheDocument();
  await waitFor(() => {
    expect(requested(fetchMock, "/api/projects?limit=21&offset=0")).toBe(1);
  });
});

test("greets the user by login", async () => {
  mockApi({});
  renderApp("/");

  expect(await screen.findByText("HI, MILA")).toBeInTheDocument();
});

test("shows PROJECT_HUB while the user loads", async () => {
  mockApi({ "GET /api/users/me": () => new Promise(() => undefined) });
  renderApp("/");

  expect(await screen.findByText("PROJECT_HUB")).toBeInTheDocument();
  expect(screen.queryByText(/^HI,/)).toBeNull();
});

test("keeps PROJECT_HUB when the user cannot be loaded", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockApi({ "GET /api/users/me": { status: 500 } });
  renderApp("/");

  await vi.advanceTimersByTimeAsync(2000);
  expect(screen.getByText("PROJECT_HUB")).toBeInTheDocument();
  expect(screen.queryByText(/something went wrong/i)).toBeNull();
});

test("lists each project with its name, description, role, owner and update", async () => {
  mockApi({ [ALL]: { status: 200, body: [owned, shared] } });
  renderApp("/projects");

  const name = await screen.findByRole("link", { name: "Website redesign" });
  expect(name).toHaveAttribute("href", `/projects/${owned.id}`);
  expect(
    screen.getAllByRole("columnheader").map((header) => header.textContent),
  ).toEqual(["Project", "Role", "Owner", "Updated"]);

  const ownedRow = within(
    screen.getByRole("row", { name: /Website redesign/ }),
  );
  expect(
    ownedRow.getByText(
      "New home page, catalogue and order form for a coffee shop",
    ),
  ).toBeInTheDocument();
  expect(ownedRow.getByText("Owner")).toBeInTheDocument();
  expect(ownedRow.getByText("mila (you)")).toBeInTheDocument();
  const ownedTime = screen
    .getByRole("row", { name: /Website redesign/ })
    .querySelector("time");
  expect(ownedTime).toHaveAttribute("datetime", owned.updated_at);
  expect(ownedTime).toHaveAttribute("title");
  expect(ownedTime?.textContent).not.toBe("");

  const sharedRow = within(
    screen.getByRole("row", { name: /Thesis materials/ }),
  );
  expect(
    sharedRow.getByRole("link", { name: "Thesis materials" }),
  ).toHaveAttribute("href", `/projects/${shared.id}`);
  expect(sharedRow.getByText("No description")).toBeInTheDocument();
  expect(sharedRow.getByText("Participant")).toBeInTheDocument();
  expect(sharedRow.getByText("sam")).toBeInTheDocument();
  expect(
    screen.getByRole("row", { name: /Thesis materials/ }).querySelector("time"),
  ).toHaveAttribute("datetime", shared.updated_at);
});

test("marks All as the current tab by default", async () => {
  mockApi({});
  renderApp("/projects");

  await screen.findByRole("navigation", { name: "Filter projects" });
  expect(tabs().getByRole("link", { name: "All" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(tabs().getByRole("link", { name: "Owned" })).not.toHaveAttribute(
    "aria-current",
  );
  expect(
    tabs().getByRole("link", { name: "Shared with me" }),
  ).not.toHaveAttribute("aria-current");
});

test("shows only owned projects on the Owned tab", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    [ALL]: { status: 200, body: [owned, shared] },
    [OWNED]: { status: 200, body: [owned] },
  });
  renderApp("/projects");

  await screen.findByRole("link", { name: "Thesis materials" });
  await user.click(tabs().getByRole("link", { name: "Owned" }));

  expect(tabs().getByRole("link", { name: "Owned" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(tabs().getByRole("link", { name: "All" })).not.toHaveAttribute(
    "aria-current",
  );
  expect(
    await screen.findByRole("link", { name: "Website redesign" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Thesis materials" })).toBeNull();
  expect(
    requested(fetchMock, "/api/projects?role=owner&limit=21&offset=0"),
  ).toBe(1);
});

test("starts on Shared with me from the address", async () => {
  mockApi({ [SHARED]: { status: 200, body: [shared] } });
  renderApp("/projects?role=participant");

  expect(
    await screen.findByRole("link", { name: "Thesis materials" }),
  ).toBeInTheDocument();
  expect(tabs().getByRole("link", { name: "Shared with me" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(tabs().getByRole("link", { name: "All" })).not.toHaveAttribute(
    "aria-current",
  );
});

test("shows All for an unknown role in the address", async () => {
  const fetchMock = mockApi({ [ALL]: { status: 200, body: [owned] } });
  renderApp("/projects?role=bogus");

  expect(
    await screen.findByRole("link", { name: "Website redesign" }),
  ).toBeInTheDocument();
  expect(tabs().getByRole("link", { name: "All" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(requested(fetchMock, "/api/projects?limit=21&offset=0")).toBe(1);
});

test.each([
  ["All", "/projects", ALL],
  ["Owned", "/projects?role=owner", OWNED],
])("invites to create the first project on %s", async (_, path, route) => {
  mockApi({ [route]: { status: 200, body: [] } });
  renderApp(path);

  expect(
    await screen.findByRole("heading", {
      level: 2,
      name: "Create your first project",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "A project keeps your documents and the people you work with in one place.",
    ),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "New project" })).toHaveLength(
    1,
  );
});

test("explains an empty Shared with me without a create button", async () => {
  mockApi({ [SHARED]: { status: 200, body: [] } });
  renderApp("/projects?role=participant");

  expect(
    await screen.findByRole("heading", {
      level: 2,
      name: "Nothing shared with you yet",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "When someone invites you to a project, it shows up here.",
    ),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "New project" })).toHaveLength(
    1,
  );
  expect(screen.queryByText("Create your first project")).toBeNull();
});

test("shows the toolbar New project button next to the list", async () => {
  mockApi({ [ALL]: { status: 200, body: [owned] } });
  renderApp("/projects");

  await screen.findByRole("link", { name: "Website redesign" });
  expect(screen.getAllByRole("button", { name: "New project" })).toHaveLength(
    1,
  );
});

test("shows placeholder rows while the list loads", async () => {
  mockApi({ [ALL]: () => new Promise(() => undefined) });
  renderApp("/projects");

  expect(
    await screen.findByRole("region", { name: "Projects" }),
  ).toHaveAttribute("aria-busy", "true");
  expect(screen.queryByText("Create your first project")).toBeNull();
});

test("offers to try again when the list fails to load", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  let failing = true;
  const fetchMock = mockApi({
    [ALL]: () => (failing ? { status: 500 } : { status: 200, body: [owned] }),
  });
  renderApp("/projects");

  await vi.advanceTimersByTimeAsync(2000);
  expect(screen.getByText("Couldn't load your projects.")).toBeInTheDocument();
  const before = requested(fetchMock, "/api/projects?limit=21&offset=0");

  failing = false;
  await user.click(screen.getByRole("button", { name: "Try again" }));

  expect(
    await screen.findByRole("link", { name: "Website redesign" }),
  ).toBeInTheDocument();
  expect(requested(fetchMock, "/api/projects?limit=21&offset=0")).toBe(
    before + 1,
  );
  expect(screen.queryByText("Couldn't load your projects.")).toBeNull();
  expect(screen.getByRole("region", { name: "Projects" })).not.toHaveAttribute(
    "aria-busy",
    "true",
  );
});

function makeProjects(count: number, from = 0): Project[] {
  return Array.from({ length: count }, (_, index) => ({
    ...owned,
    id: `20000000-0000-4000-8000-${String(from + index).padStart(12, "0")}`,
    name: `Project ${String(from + index + 1)}`,
  }));
}

const PAGE_2 = "GET /api/projects?limit=21&offset=20";

function projectRows() {
  return screen.getAllByRole("row").slice(1);
}

test("shows 20 rows and Show more when there is a next page, then loads it", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: { status: 200, body: makeProjects(5, 20) },
  });
  renderApp("/projects");

  await screen.findByRole("link", { name: "Project 1" });
  expect(projectRows()).toHaveLength(20);
  expect(screen.queryByRole("link", { name: "Project 21" })).toBeNull();

  await user.click(screen.getByRole("button", { name: "Show more" }));

  expect(
    await screen.findByRole("link", { name: "Project 25" }),
  ).toBeInTheDocument();
  expect(projectRows()).toHaveLength(25);
  expect(requested(fetchMock, "/api/projects?limit=21&offset=20")).toBe(1);
  expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
});

test("hides Show more when the first page is exactly 20 projects", async () => {
  mockApi({ [ALL]: { status: 200, body: makeProjects(20) } });
  renderApp("/projects");

  await screen.findByRole("link", { name: "Project 20" });
  expect(projectRows()).toHaveLength(20);
  expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
});

test("keeps Show more busy and sends one request on a second click", async () => {
  const user = userEvent.setup();
  let release: () => void = () => undefined;
  const fetchMock = mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 200, body: makeProjects(5, 20) });
        };
      }),
  });
  renderApp("/projects");

  const button = await screen.findByRole("button", { name: "Show more" });
  await user.click(button);
  await waitFor(() => {
    expect(button).toHaveAttribute("aria-busy", "true");
  });
  await user.click(button);

  expect(requested(fetchMock, "/api/projects?limit=21&offset=20")).toBe(1);

  release();
  expect(
    await screen.findByRole("link", { name: "Project 25" }),
  ).toBeInTheDocument();
});

test("keeps the loaded rows and offers to try again when the next page fails", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  let failing = true;
  const fetchMock = mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: () =>
      failing ? { status: 500 } : { status: 200, body: makeProjects(5, 20) },
  });
  renderApp("/projects");

  await vi.advanceTimersByTimeAsync(0);
  await user.click(await screen.findByRole("button", { name: "Show more" }));
  await vi.advanceTimersByTimeAsync(2000);

  expect(screen.getByText("Couldn't load your projects.")).toBeInTheDocument();
  expect(projectRows()).toHaveLength(20);
  expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
  const before = requested(fetchMock, "/api/projects?limit=21&offset=20");

  failing = false;
  await user.click(screen.getByRole("button", { name: "Try again" }));

  expect(
    await screen.findByRole("link", { name: "Project 25" }),
  ).toBeInTheDocument();
  expect(requested(fetchMock, "/api/projects?limit=21&offset=20")).toBe(
    before + 1,
  );
  expect(projectRows()).toHaveLength(25);
  expect(screen.queryByText("Couldn't load your projects.")).toBeNull();
});

test("starts another tab on its first page and keeps loaded pages when you come back", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: { status: 200, body: makeProjects(20, 20) },
    [OWNED]: { status: 200, body: [owned] },
  });
  renderApp("/projects");

  await user.click(await screen.findByRole("button", { name: "Show more" }));
  await screen.findByRole("link", { name: "Project 40" });
  expect(projectRows()).toHaveLength(40);

  await user.click(tabs().getByRole("link", { name: "Owned" }));

  await screen.findByRole("link", { name: "Website redesign" });
  expect(projectRows()).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
  expect(
    requested(fetchMock, "/api/projects?role=owner&limit=21&offset=0"),
  ).toBe(1);

  await user.click(tabs().getByRole("link", { name: "All" }));

  expect(await screen.findByRole("link", { name: "Project 40" })).toBeVisible();
  expect(projectRows()).toHaveLength(40);
  expect(requested(fetchMock, "/api/projects?limit=21&offset=0")).toBe(1);
  expect(requested(fetchMock, "/api/projects?limit=21&offset=20")).toBe(1);
});

test("keeps the rows and shows no next-page error when a background refresh fails", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  let failing = false;
  mockApi({
    [ALL]: () =>
      failing ? { status: 500 } : { status: 200, body: makeProjects(21) },
    [OWNED]: { status: 200, body: [owned] },
  });
  renderApp("/projects");
  await screen.findByRole("button", { name: "Show more" });
  await user.click(tabs().getByRole("link", { name: "Owned" }));
  await screen.findByRole("link", { name: "Website redesign" });

  failing = true;
  await vi.advanceTimersByTimeAsync(31_000);
  await user.click(tabs().getByRole("link", { name: "All" }));
  await vi.advanceTimersByTimeAsync(3000);

  expect(projectRows()).toHaveLength(20);
  expect(screen.queryByText("Couldn't load your projects.")).toBeNull();
  expect(screen.getByRole("button", { name: "Show more" })).toBeVisible();
});

test("moves focus to the first new project when the last page loads", async () => {
  const user = userEvent.setup();
  let release: () => void = () => undefined;
  mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 200, body: makeProjects(5, 20) });
        };
      }),
  });
  renderApp("/projects");

  const button = await screen.findByRole("button", { name: "Show more" });
  await user.click(button);
  await waitFor(() => {
    expect(button).toHaveAttribute("aria-busy", "true");
  });
  expect(document.activeElement).toBe(button);

  release();
  const first = await screen.findByRole("link", { name: "Project 21" });
  await waitFor(() => {
    expect(document.activeElement).toBe(first);
  });
});

test("keeps focus on Show more when more pages remain", async () => {
  const user = userEvent.setup();
  mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: { status: 200, body: makeProjects(21, 20) },
  });
  renderApp("/projects");

  await user.click(await screen.findByRole("button", { name: "Show more" }));

  await screen.findByRole("link", { name: "Project 40" });
  expect(document.activeElement).toBe(
    screen.getByRole("button", { name: "Show more" }),
  );
});

test("keeps focus on the tab when switching to a cached tab while Show more loads", async () => {
  const user = userEvent.setup();
  let release: () => void = () => undefined;
  mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 200, body: makeProjects(5, 20) });
        };
      }),
    [OWNED]: { status: 200, body: makeProjects(21, 100) },
  });
  renderApp("/projects?role=owner");
  await screen.findByRole("link", { name: "Project 101" });
  await user.click(tabs().getByRole("link", { name: "All" }));
  const button = await screen.findByRole("button", { name: "Show more" });
  await screen.findByRole("link", { name: "Project 1" });
  await user.click(button);
  await waitFor(() => {
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  const ownedTab = tabs().getByRole("link", { name: "Owned" });
  await user.click(ownedTab);
  await screen.findByRole("link", { name: "Project 101" });

  expect(document.activeElement).toBe(ownedTab);
  release();
  const allTab = tabs().getByRole("link", { name: "All" });
  await user.click(allTab);
  await screen.findByRole("link", { name: "Project 21" });

  expect(document.activeElement).toBe(allTab);
});

test("moves focus to Try again when the next page fails, then to the new project", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  let failing = true;
  mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: () =>
      failing ? { status: 500 } : { status: 200, body: makeProjects(5, 20) },
  });
  renderApp("/projects");

  await user.click(await screen.findByRole("button", { name: "Show more" }));
  await vi.advanceTimersByTimeAsync(2000);
  const retry = screen.getByRole("button", { name: "Try again" });
  expect(document.activeElement).toBe(retry);

  failing = false;
  await user.click(retry);

  const first = await screen.findByRole("link", { name: "Project 21" });
  await waitFor(() => {
    expect(document.activeElement).toBe(first);
  });
});

test("moves focus back to Show more when a retry succeeds and more pages remain", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  let failing = true;
  mockApi({
    [ALL]: { status: 200, body: makeProjects(21) },
    [PAGE_2]: () =>
      failing ? { status: 500 } : { status: 200, body: makeProjects(21, 20) },
  });
  renderApp("/projects");

  await user.click(await screen.findByRole("button", { name: "Show more" }));
  await vi.advanceTimersByTimeAsync(2000);
  failing = false;
  await user.click(screen.getByRole("button", { name: "Try again" }));

  await screen.findByRole("link", { name: "Project 40" });
  await waitFor(() => {
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Show more" }),
    );
  });
});
