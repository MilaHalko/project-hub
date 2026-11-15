import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const PROJECT_ID = "10000000-0000-4000-8000-000000000001";
const INFO = `/api/project/${PROJECT_ID}/info`;
const DELETE = `DELETE /api/project/${PROJECT_ID}`;

const existing: Project = {
  id: PROJECT_ID,
  name: "Website redesign",
  description: "",
  owner: { id: "00000000-0000-4000-8000-000000000001", login: "mila" },
  my_role: "owner",
  created_at: "2026-11-15T10:00:00Z",
  updated_at: "2026-11-15T10:00:00Z",
};

function routes(extra: Parameters<typeof mockApi>[0] = {}) {
  return mockApi({
    [`GET ${INFO}`]: { status: 200, body: existing },
    ...extra,
  });
}

function requests(fetchMock: ReturnType<typeof mockApi>, method: string) {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === method);
}

function infoGets(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      url === INFO && (init?.method === undefined || init.method === "GET"),
  );
}

async function openDelete() {
  const user = userEvent.setup();
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
  await user.click(screen.getByRole("button", { name: "Delete project" }));
  const dialog = await screen.findByRole("alertdialog", {
    name: "Delete this project?",
  });
  return { user, dialog };
}

function confirmButton(dialog: HTMLElement) {
  return within(dialog).getByRole("button", { name: "Delete project" });
}

test("asks to type the project name and keeps Delete project disabled", async () => {
  routes();
  const { dialog } = await openDelete();

  expect(
    within(dialog).getByText(
      (_, node) =>
        node?.tagName === "P" &&
        node.textContent ===
          "This deletes Website redesign with all its documents and removes everyone's access. You can't undo this.",
    ),
  ).toBeInTheDocument();
  expect(within(dialog).getByText("Website redesign").tagName).toBe("STRONG");
  expect(
    within(dialog).getByRole("textbox", {
      name: "Type the project name to confirm",
    }),
  ).toBeInTheDocument();
  expect(
    within(dialog).getByRole("button", { name: "Cancel" }),
  ).toBeInTheDocument();
  expect(confirmButton(dialog)).toBeDisabled();
  expect(dialog).toHaveAccessibleDescription(
    "This deletes Website redesign with all its documents and removes everyone's access. You can't undo this.",
  );
});

test("stays disabled for part of the name or the name in another case", async () => {
  routes();
  const { user, dialog } = await openDelete();
  const field = within(dialog).getByRole("textbox", {
    name: "Type the project name to confirm",
  });

  await user.type(field, "Website");
  expect(confirmButton(dialog)).toBeDisabled();

  await user.clear(field);
  await user.type(field, "website redesign");
  expect(confirmButton(dialog)).toBeDisabled();
});

test("enables for the name with spaces around it", async () => {
  routes();
  const { user, dialog } = await openDelete();

  await user.type(
    within(dialog).getByRole("textbox", {
      name: "Type the project name to confirm",
    }),
    "  Website redesign ",
  );

  expect(confirmButton(dialog)).toBeEnabled();
});

async function typeName(
  user: ReturnType<typeof userEvent.setup>,
  dialog: HTMLElement,
) {
  await user.type(
    within(dialog).getByRole("textbox", {
      name: "Type the project name to confirm",
    }),
    "Website redesign",
  );
}

test("deletes once on a double click, opens the list and shows a toast", async () => {
  let release: () => void = () => undefined;
  const fetchMock = routes({
    [DELETE]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 204 });
        };
      }),
  });
  const { user, dialog } = await openDelete();
  await typeName(user, dialog);

  await user.dblClick(confirmButton(dialog));

  expect(requests(fetchMock, "DELETE")).toHaveLength(1);
  release();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Project deleted")).toBeInTheDocument();
  expect(screen.queryByRole("alertdialog")).toBeNull();
  expect(requests(fetchMock, "DELETE")).toHaveLength(1);
  expect(infoGets(fetchMock)).toHaveLength(1);
  expect(screen.queryByText("Project not found")).toBeNull();
});

function listed(count: number, from: number, targetAt: number): Project[] {
  return Array.from({ length: count }, (_, index) =>
    from + index === targetAt
      ? existing
      : {
          ...existing,
          id: `20000000-0000-4000-8000-${String(from + index).padStart(12, "0")}`,
          name: `Project ${String(from + index + 1)}`,
        },
  );
}

async function deleteFromTwoLoadedPages(targetAt: number) {
  const user = userEvent.setup();
  const answered: Record<string, number> = {};
  function heldAfterFirst(first: Project[]) {
    return (key: string) => () => {
      answered[key] = (answered[key] ?? 0) + 1;
      if (answered[key] === 1) return { status: 200, body: first };
      return new Promise<never>(() => undefined);
    };
  }
  const page1 = "GET /api/projects?limit=21&offset=0";
  const page2 = "GET /api/projects?limit=21&offset=20";
  routes({
    [page1]: heldAfterFirst(listed(21, 0, targetAt))(page1),
    [page2]: heldAfterFirst(listed(21, 20, targetAt))(page2),
    [DELETE]: { status: 204 },
  });
  renderApp("/projects");
  await user.click(await screen.findByRole("button", { name: "Show more" }));
  await screen.findByRole("link", { name: "Project 40" });
  await user.click(screen.getByRole("link", { name: "Website redesign" }));
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
  await user.click(screen.getByRole("button", { name: "Delete project" }));
  const dialog = await screen.findByRole("alertdialog", {
    name: "Delete this project?",
  });
  await typeName(user, dialog);
  await user.click(confirmButton(dialog));
  await screen.findByText("Project deleted");
  await screen.findByRole("link", { name: "Project 2" });
}

function listedNames(): string[] {
  return within(screen.getByRole("region", { name: "Projects" }))
    .getAllByRole("link")
    .map((link) => link.textContent);
}

test("keeps every row once and Show more after deleting from the first of two pages", async () => {
  await deleteFromTwoLoadedPages(0);

  const names = listedNames();
  expect(names).not.toContain("Website redesign");
  expect(new Set(names).size).toBe(names.length);
  expect(names).toHaveLength(39);
  expect(screen.getByRole("button", { name: "Show more" })).toBeVisible();
});

test("keeps every row once after deleting from a full last page", async () => {
  await deleteFromTwoLoadedPages(24);

  const names = listedNames();
  expect(names).not.toContain("Website redesign");
  expect(new Set(names).size).toBe(names.length);
  expect(names).toContain("Project 41");
});

test("removes the project from the list before the list reloads", async () => {
  const user = userEvent.setup();
  const other: Project = {
    ...existing,
    id: "10000000-0000-4000-8000-000000000002",
    name: "Thesis materials",
  };
  let listed = 0;
  const waiting: (() => void)[] = [];
  routes({
    "GET /api/projects?limit=21&offset=0": () => {
      listed += 1;
      if (listed === 1) return { status: 200, body: [existing, other] };
      return new Promise((resolve) => {
        waiting.push(() => {
          resolve({ status: 200, body: [other] });
        });
      });
    },
    [DELETE]: { status: 204 },
  });
  renderApp("/projects");
  await user.click(
    await screen.findByRole("link", { name: "Website redesign" }),
  );
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
  await user.click(screen.getByRole("button", { name: "Delete project" }));
  const dialog = await screen.findByRole("alertdialog", {
    name: "Delete this project?",
  });
  await typeName(user, dialog);

  await user.click(confirmButton(dialog));

  expect(await screen.findByText("Project deleted")).toBeInTheDocument();
  expect(
    await screen.findByRole("link", { name: "Thesis materials" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Website redesign" })).toBeNull();
  await waitFor(() => {
    expect(waiting.length).toBeGreaterThan(0);
  });
  for (const release of waiting) release();
  await waitFor(() => {
    expect(
      screen.getByRole("region", { name: "Projects" }),
    ).not.toHaveAttribute("aria-busy");
  });
  expect(screen.queryByRole("link", { name: "Website redesign" })).toBeNull();
});

test("shows the permission message in the dialog on 403", async () => {
  routes({ [DELETE]: { status: 403 } });
  const { user, dialog } = await openDelete();
  await typeName(user, dialog);

  await user.click(confirmButton(dialog));

  expect(await within(dialog).findByRole("alert")).toHaveTextContent(
    "You don't have permission to do this.",
  );
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
});

test("goes to the list with a toast when the project no longer exists", async () => {
  routes({ [DELETE]: { status: 404 } });
  const { user, dialog } = await openDelete();
  await typeName(user, dialog);

  await user.click(confirmButton(dialog));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("This project no longer exists."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("alertdialog")).toBeNull();
});

test("shows a retry message in the dialog when the network fails", async () => {
  routes({
    [DELETE]: () => {
      throw new Error("offline");
    },
  });
  const { user, dialog } = await openDelete();
  await typeName(user, dialog);

  await user.click(confirmButton(dialog));

  expect(await within(dialog).findByRole("alert")).toHaveTextContent(
    "Couldn't delete the project. Try again.",
  );
  expect(
    within(dialog).getByRole("textbox", {
      name: "Type the project name to confirm",
    }),
  ).toHaveValue("Website redesign");
  expect(confirmButton(dialog)).toBeEnabled();
});

test("keeps the dialog open on Cancel and Escape during the request", async () => {
  let release: () => void = () => undefined;
  routes({
    [DELETE]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 204 });
        };
      }),
  });
  const { user, dialog } = await openDelete();
  await typeName(user, dialog);
  await user.click(confirmButton(dialog));
  await waitFor(() => {
    expect(confirmButton(dialog)).toHaveAttribute("aria-busy", "true");
  });

  expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeDisabled();
  fireEvent(dialog, new Event("cancel", { cancelable: true }));

  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  release();
  await waitFor(() => {
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });
});

test("ignores Esc pressed right after Delete project, before the page updates", async () => {
  let release: () => void = () => undefined;
  routes({
    [DELETE]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 204 });
        };
      }),
  });
  const { user, dialog } = await openDelete();
  await typeName(user, dialog);

  fireEvent.click(confirmButton(dialog));
  fireEvent(dialog, new Event("cancel", { cancelable: true }));

  expect(dialog).toHaveAttribute("open");
  await waitFor(() => {
    expect(confirmButton(dialog)).toHaveAttribute("aria-busy", "true");
  });
  release();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});

test("Cancel closes the dialog and clears the field", async () => {
  routes();
  const { user, dialog } = await openDelete();
  await typeName(user, dialog);

  await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
  await waitFor(() => {
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });
  await user.click(screen.getByRole("button", { name: "Delete project" }));

  const reopened = await screen.findByRole("alertdialog", {
    name: "Delete this project?",
  });
  expect(
    within(reopened).getByRole("textbox", {
      name: "Type the project name to confirm",
    }),
  ).toHaveValue("");
});
