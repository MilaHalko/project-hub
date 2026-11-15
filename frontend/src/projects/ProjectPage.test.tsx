import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

afterEach(() => {
  vi.useRealTimers();
});

const OWNED_ID = "10000000-0000-4000-8000-000000000001";
const SHARED_ID = "10000000-0000-4000-8000-000000000002";

const owned: Project = {
  id: OWNED_ID,
  name: "Website redesign",
  description: "Line one\nLine two",
  owner: { id: "00000000-0000-4000-8000-000000000001", login: "mila" },
  my_role: "owner",
  created_at: "2026-11-12T10:00:00Z",
  updated_at: "2026-11-14T09:30:00Z",
};

const shared: Project = {
  id: SHARED_ID,
  name: "Thesis materials",
  description: "Chapter drafts",
  owner: { id: "00000000-0000-4000-8000-000000000002", login: "sam" },
  my_role: "participant",
  created_at: "2026-10-28T08:00:00Z",
  updated_at: "2026-11-13T16:00:00Z",
};

function infoOf(id: string) {
  return `GET /api/project/${id}/info`;
}

function detail(term: string): HTMLElement {
  const dt = screen.getByText(term, { selector: "dt" });
  const dd = dt.nextElementSibling;
  if (!(dd instanceof HTMLElement)) throw new Error(`No value for ${term}`);
  return dd;
}

test("shows the owner's project with its header and details", async () => {
  mockApi({ [infoOf(OWNED_ID)]: { status: 200, body: owned } });
  renderApp(`/projects/${OWNED_ID}`);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeInTheDocument();
  const crumbs = screen.getByRole("navigation", { name: "Breadcrumb" });
  expect(
    within(crumbs).getByRole("link", { name: "Projects" }),
  ).toHaveAttribute("href", "/projects");
  expect(within(crumbs).getByText("Website redesign")).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.getByText("Owner", { selector: "span" })).toBeInTheDocument();
  const description = screen.getByText(/Line one/);
  expect(description.textContent).toBe("Line one\nLine two");
  expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Delete project" }),
  ).toBeInTheDocument();
  expect(detail("Owner")).toHaveTextContent("mila (you)");
  expect(detail("Created")).toHaveTextContent("Nov 12, 2026");
  const updated = detail("Updated");
  expect(updated.textContent).toMatch(/ago|yesterday|Nov 14/);
  expect(updated).toHaveAttribute(
    "title",
    expect.stringContaining("Nov 14, 2026"),
  );
  expect(document.title).toBe("Website redesign — Project Hub");
});

test("restores the tab title when leaving the page", async () => {
  const user = userEvent.setup();
  mockApi({ [infoOf(OWNED_ID)]: { status: 200, body: owned } });
  renderApp(`/projects/${OWNED_ID}`);
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });

  await user.click(
    within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole(
      "link",
      { name: "Projects" },
    ),
  );

  await screen.findByRole("heading", { level: 1, name: "Your projects" });
  expect(document.title).toBe("Project Hub");
});

test("shows a participant's project without Delete project", async () => {
  mockApi({ [infoOf(SHARED_ID)]: { status: 200, body: shared } });
  renderApp(`/projects/${SHARED_ID}`);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Thesis materials" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Participant", { selector: "span" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Delete project" })).toBeNull();
  expect(detail("Owner")).toHaveTextContent(/^sam$/);
});

test("shows a name that looks like HTML as plain text", async () => {
  const name = "<img src=x onerror=alert(1)>";
  mockApi({
    [infoOf(OWNED_ID)]: {
      status: 200,
      body: { ...owned, name, description: name },
    },
  });
  const { container } = renderApp(`/projects/${OWNED_ID}`);

  expect(
    await screen.findByRole("heading", { level: 1, name }),
  ).toBeInTheDocument();
  expect(container.querySelector("img")).toBeNull();
  expect(document.querySelector("img")).toBeNull();
});

test.each([
  ["404", OWNED_ID, { status: 404, body: { detail: "Project not found" } }],
  ["422", "abc", { status: 422, body: { detail: "Invalid id" } }],
])("shows not found for a %s answer", async (_label, id, answer) => {
  const user = userEvent.setup();
  mockApi({ [infoOf(id)]: answer });
  renderApp(`/projects/${id}`);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Project not found" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "It may have been deleted, or you don't have access to it.",
    ),
  ).toBeInTheDocument();
  const link = screen.getByRole("link", { name: "Back to projects" });
  expect(link).toHaveAttribute("href", "/projects");

  await user.click(link);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test("offers Try again when the project cannot be loaded", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  let failing = true;
  const fetchMock = mockApi({
    [infoOf(OWNED_ID)]: () =>
      failing ? { status: 500 } : { status: 200, body: owned },
  });
  renderApp(`/projects/${OWNED_ID}`);

  await vi.advanceTimersByTimeAsync(2000);
  expect(screen.getByText("Couldn't load the project.")).toBeInTheDocument();
  const before = fetchMock.mock.calls.filter(
    ([url]) => url === `/api/project/${OWNED_ID}/info`,
  ).length;

  failing = false;
  await user.click(screen.getByRole("button", { name: "Try again" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeInTheDocument();
  const after = fetchMock.mock.calls.filter(
    ([url]) => url === `/api/project/${OWNED_ID}/info`,
  ).length;
  expect(after).toBeGreaterThan(before);
});

test("shows a skeleton banner while the project loads", async () => {
  mockApi({ [infoOf(OWNED_ID)]: () => new Promise(() => undefined) });
  renderApp(`/projects/${OWNED_ID}`);

  await screen.findByRole("navigation", { name: "Breadcrumb" });
  expect(
    screen.getByRole("status", { name: "Loading project" }),
  ).toHaveAttribute("aria-busy", "true");
  expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
});
