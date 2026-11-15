import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const CREATE = "POST /api/projects";

const created: Project = {
  id: "10000000-0000-4000-8000-000000000009",
  name: "Website redesign",
  description: "New home page",
  owner: { id: "00000000-0000-4000-8000-000000000001", login: "mila" },
  my_role: "owner",
  created_at: "2026-11-15T10:00:00Z",
  updated_at: "2026-11-15T10:00:00Z",
};

function posts(
  fetchMock: ReturnType<typeof mockApi>,
): Parameters<typeof fetch>[] {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");
}

async function openDialog() {
  const user = userEvent.setup();
  renderApp("/projects");
  await screen.findByRole("heading", { name: "Create your first project" });
  await user.click(screen.getByRole("button", { name: "New project" }));
  await screen.findByRole("dialog", { name: "New project" });
  return { user };
}

test("opens a dialog with the name focused and a description counter", async () => {
  mockApi({});
  const { user } = await openDialog();

  expect(screen.getByRole("textbox", { name: "Name" })).toHaveFocus();
  expect(screen.getByText("0 / 2000")).toBeInTheDocument();

  await user.type(
    screen.getByRole("textbox", { name: "Description (optional)" }),
    "Hello",
  );

  expect(screen.getByText("5 / 2000")).toBeInTheDocument();
});

test("counts an emoji as one character in the description counter", async () => {
  mockApi({});
  const { user } = await openDialog();
  await user.click(
    screen.getByRole("textbox", { name: "Description (optional)" }),
  );

  await user.paste("😀😀😀");

  expect(screen.getByText("3 / 2000")).toBeInTheDocument();
});

test("shows a message next to Description and sends nothing for 2001 characters", async () => {
  const fetchMock = mockApi({});
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");
  await user.click(
    screen.getByRole("textbox", { name: "Description (optional)" }),
  );
  await user.paste("d".repeat(2001));

  await user.click(screen.getByRole("button", { name: "Create project" }));

  expect(
    screen.getByRole("textbox", { name: "Description (optional)" }),
  ).toHaveAccessibleDescription(
    expect.stringContaining("Use 2000 characters or fewer."),
  );
  expect(posts(fetchMock)).toHaveLength(0);
});

test("shows a message next to Name and sends nothing for an empty name", async () => {
  const fetchMock = mockApi({});
  const { user } = await openDialog();

  await user.click(screen.getByRole("button", { name: "Create project" }));

  expect(screen.getByText("Enter a project name.")).toBeInTheDocument();
  expect(
    screen.getByRole("textbox", { name: "Name" }),
  ).toHaveAccessibleDescription("Enter a project name.");
  expect(posts(fetchMock)).toHaveLength(0);
});

test("keeps checking while typing after the first submit", async () => {
  mockApi({});
  const { user } = await openDialog();
  await user.click(screen.getByRole("button", { name: "Create project" }));

  await user.type(screen.getByRole("textbox", { name: "Name" }), "a");

  expect(screen.queryByText("Enter a project name.")).toBeNull();
});

test("creates the project with a trimmed name and opens its page", async () => {
  const fetchMock = mockApi({
    [CREATE]: { status: 201, body: created },
  });
  const { user } = await openDialog();
  await user.type(
    screen.getByRole("textbox", { name: "Name" }),
    "  Website redesign ",
  );
  await user.type(
    screen.getByRole("textbox", { name: "Description (optional)" }),
    "New home page",
  );

  await user.click(screen.getByRole("button", { name: "Create project" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Website redesign" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Project created")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).toBeNull();
  const [post] = posts(fetchMock);
  const url = post?.[0];
  const body = post?.[1]?.body;
  expect(url).toBe("/api/projects");
  expect(JSON.parse(body as string)).toEqual({
    name: "Website redesign",
    description: "New home page",
  });
  expect(
    fetchMock.mock.calls.filter(
      ([input]) => typeof input === "string" && input.includes("/info"),
    ),
  ).toHaveLength(0);
});

test("refreshes the lists after creating", async () => {
  let listed = 0;
  mockApi({
    "GET /api/projects?limit=21&offset=0": () => {
      listed += 1;
      return { status: 200, body: [] };
    },
    [CREATE]: { status: 201, body: created },
  });
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");
  await user.click(screen.getByRole("button", { name: "Create project" }));
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });

  await user.click(
    within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole(
      "link",
      { name: "Projects" },
    ),
  );

  await waitFor(() => {
    expect(listed).toBe(2);
  });
});

test("shows the new project, not the empty list, when going back before the list reloads", async () => {
  let listed = 0;
  const waiting: (() => void)[] = [];
  mockApi({
    "GET /api/projects?limit=21&offset=0": () => {
      listed += 1;
      if (listed === 1) return { status: 200, body: [] };
      return new Promise((resolve) => {
        waiting.push(() => {
          resolve({ status: 200, body: [created] });
        });
      });
    },
    [CREATE]: { status: 201, body: created },
  });
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");
  await user.click(screen.getByRole("button", { name: "Create project" }));
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });

  await user.click(
    within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole(
      "link",
      { name: "Projects" },
    ),
  );

  await screen.findByRole("heading", { level: 1, name: "Your projects" });
  expect(
    screen.queryByRole("heading", { name: "Create your first project" }),
  ).toBeNull();
  await waitFor(() => {
    expect(waiting.length).toBeGreaterThan(0);
  });
  for (const release of waiting) release();
  expect(
    await screen.findByRole("link", { name: "Website redesign" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Create your first project" }),
  ).toBeNull();
});

test("sends one request for a double click", async () => {
  let release: () => void = () => undefined;
  const fetchMock = mockApi({
    [CREATE]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 201, body: created });
        };
      }),
  });
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");

  await user.dblClick(screen.getByRole("button", { name: "Create project" }));

  expect(posts(fetchMock)).toHaveLength(1);
  release();
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
  expect(posts(fetchMock)).toHaveLength(1);
});

test("shows a 422 field error next to Name", async () => {
  mockApi({
    [CREATE]: {
      status: 422,
      body: {
        detail: [
          {
            loc: ["body", "name"],
            msg: "Value error, Name is taken",
            type: "value_error",
          },
        ],
      },
    },
  });
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");

  await user.click(screen.getByRole("button", { name: "Create project" }));

  expect(await screen.findByText("Name is taken")).toBeInTheDocument();
  expect(
    screen.getByRole("textbox", { name: "Name" }),
  ).toHaveAccessibleDescription("Name is taken");
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});

test("shows a 422 field error for a name edited while the request was pending", async () => {
  let release: () => void = () => undefined;
  mockApi({
    [CREATE]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({
            status: 422,
            body: {
              detail: [
                {
                  loc: ["body", "name"],
                  msg: "Value error, Name is taken",
                  type: "value_error",
                },
              ],
            },
          });
        };
      }),
  });
  const { user } = await openDialog();
  const name = screen.getByRole("textbox", { name: "Name" });
  await user.type(name, "Website");
  await user.click(screen.getByRole("button", { name: "Create project" }));
  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: "Create project" }),
    ).toHaveAttribute("aria-busy", "true");
  });

  await user.type(name, "!");
  release();

  expect(await screen.findByText("Name is taken")).toBeInTheDocument();
  expect(name).toHaveAccessibleDescription("Name is taken");
});

test("shows a 422 message above the buttons", async () => {
  mockApi({
    [CREATE]: { status: 422, body: { detail: "Name must not be reserved" } },
  });
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");

  await user.click(screen.getByRole("button", { name: "Create project" }));

  expect(
    await within(screen.getByRole("dialog")).findByRole("alert"),
  ).toHaveTextContent("Name must not be reserved");
});

test("keeps what was typed when the network fails", async () => {
  mockApi({
    [CREATE]: () => {
      throw new Error("offline");
    },
  });
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");
  await user.type(
    screen.getByRole("textbox", { name: "Description (optional)" }),
    "Notes",
  );

  await user.click(screen.getByRole("button", { name: "Create project" }));

  expect(
    await within(screen.getByRole("dialog")).findByRole("alert"),
  ).toHaveTextContent("Couldn't create the project. Try again.");
  expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("Website");
  expect(
    screen.getByRole("textbox", { name: "Description (optional)" }),
  ).toHaveValue("Notes");
});

test("closes with Cancel and sends nothing", async () => {
  const fetchMock = mockApi({});
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");

  await user.click(screen.getByRole("button", { name: "Cancel" }));

  expect(screen.queryByRole("dialog")).toBeNull();
  expect(posts(fetchMock)).toHaveLength(0);
});

test("opens empty again after being closed", async () => {
  mockApi({});
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");
  await user.click(screen.getByRole("button", { name: "Cancel" }));

  await user.click(screen.getByRole("button", { name: "New project" }));

  expect(await screen.findByRole("textbox", { name: "Name" })).toHaveValue("");
});

function pendingCreate() {
  let release: () => void = () => undefined;
  mockApi({
    [CREATE]: () =>
      new Promise((resolve) => {
        release = () => {
          resolve({ status: 201, body: created });
        };
      }),
  });
  return {
    release: () => {
      release();
    },
  };
}

async function submitAndWait(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");
  await user.click(screen.getByRole("button", { name: "Create project" }));
  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: "Create project" }),
    ).toHaveAttribute("aria-busy", "true");
  });
}

test("keeps the dialog open when Cancel is clicked during the request", async () => {
  const request = pendingCreate();
  const { user } = await openDialog();
  await submitAndWait(user);

  await user.click(screen.getByRole("button", { name: "Cancel" }));

  expect(screen.getByRole("dialog")).toBeInTheDocument();
  request.release();
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
});

test("ignores the native cancel (Esc) during the request", async () => {
  const request = pendingCreate();
  const { user } = await openDialog();
  await submitAndWait(user);

  fireEvent(
    screen.getByRole("dialog"),
    new Event("cancel", { cancelable: true }),
  );

  expect(screen.getByRole("dialog")).toBeInTheDocument();
  request.release();
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
});

test("ignores Esc pressed right after Create project, before the page updates", async () => {
  const request = pendingCreate();
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");
  const dialog = screen.getByRole("dialog");

  fireEvent.click(screen.getByRole("button", { name: "Create project" }));
  fireEvent(dialog, new Event("cancel", { cancelable: true }));

  expect(dialog).toHaveAttribute("open");
  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: "Create project" }),
    ).toHaveAttribute("aria-busy", "true");
  });
  request.release();
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
});

test("opens the dialog again when the browser closes it during the request", async () => {
  const request = pendingCreate();
  const { user } = await openDialog();
  await submitAndWait(user);
  const dialog = screen.getByRole("dialog");
  const create = screen.getByRole("button", { name: "Create project" });
  create.focus();

  fireEvent(dialog, new Event("cancel"));
  dialog.removeAttribute("open");
  screen.getByRole("button", { name: "New project", hidden: true }).focus();
  fireEvent(dialog, new Event("close"));

  await waitFor(() => {
    expect(dialog).toHaveAttribute("open");
  });
  expect(create).toHaveFocus();
  request.release();
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
});

test("closes the dialog when the browser closes it natively", async () => {
  mockApi({});
  await openDialog();

  screen.getByRole("dialog").dispatchEvent(new Event("close"));

  await waitFor(() => {
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

test("shows the fallback when a 422 names no known field", async () => {
  mockApi({
    [CREATE]: {
      status: 422,
      body: {
        detail: [{ loc: ["body", "owner"], msg: "Nope", type: "value_error" }],
      },
    },
  });
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");

  await user.click(screen.getByRole("button", { name: "Create project" }));

  expect(
    await within(screen.getByRole("dialog")).findByRole("alert"),
  ).toHaveTextContent("Couldn't create the project. Try again.");
});

test("clears a server field error once the field is edited", async () => {
  mockApi({
    [CREATE]: {
      status: 422,
      body: {
        detail: [
          {
            loc: ["body", "name"],
            msg: "Value error, Name is taken",
            type: "value_error",
          },
        ],
      },
    },
  });
  const { user } = await openDialog();
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Website");
  await user.click(screen.getByRole("button", { name: "Create project" }));
  await screen.findByText("Name is taken");

  await user.type(screen.getByRole("textbox", { name: "Name" }), "2");

  expect(screen.queryByText("Name is taken")).toBeNull();
});
