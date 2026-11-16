import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import {
  brief,
  documentRoute,
  infoRoute,
  listRoute,
  project,
  PROJECT_ID,
} from "./testData";

const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:saved");
const revokeObjectURL = vi.fn();
const clicked: HTMLAnchorElement[] = [];

beforeEach(() => {
  Object.assign(URL, { createObjectURL, revokeObjectURL });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicked.push(this);
  });
});

afterEach(() => {
  createObjectURL.mockClear();
  revokeObjectURL.mockClear();
  clicked.length = 0;
  vi.restoreAllMocks();
});

async function openPage(routes: Parameters<typeof mockApi>[0]) {
  const fetchMock = mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [brief] },
    ...routes,
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("Client brief.pdf");
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof mockApi>, url: string) {
  return fetchMock.mock.calls.filter(
    ([called, init]) => called === url && (init?.method ?? "GET") === "GET",
  );
}

test("saves the file under the document's name", async () => {
  const bytes = new Blob(["%PDF-1.4"], { type: "application/pdf" });
  const fetchMock = await openPage({
    [documentRoute("GET", brief.id)]: { status: 200, body: bytes },
  });
  const user = userEvent.setup();

  await user.dblClick(
    screen.getByRole("button", { name: "Download Client brief.pdf" }),
  );

  await vi.waitFor(() => {
    expect(clicked).toHaveLength(1);
  });
  expect(calls(fetchMock, `/api/document/${brief.id}`)).toHaveLength(1);
  const saved = createObjectURL.mock.calls[0]?.[0];
  expect(await saved?.text()).toBe("%PDF-1.4");
  expect(clicked[0]?.download).toBe("Client brief.pdf");
  expect(clicked[0]?.getAttribute("href")).toBe("blob:saved");
  await vi.waitFor(
    () => {
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:saved");
    },
    { timeout: 2000 },
  );
});

test("says when the document is gone and reloads the list", async () => {
  const fetchMock = await openPage({
    [documentRoute("GET", brief.id)]: {
      status: 404,
      body: { detail: "Document not found" },
    },
  });

  await userEvent.click(
    screen.getByRole("button", { name: "Download Client brief.pdf" }),
  );

  expect(
    await screen.findByText(
      "This document no longer exists. Someone may have deleted it.",
    ),
  ).toBeInTheDocument();
  await vi.waitFor(() => {
    expect(
      calls(fetchMock, `/api/project/${PROJECT_ID}/documents`),
    ).toHaveLength(2);
  });
  expect(clicked).toHaveLength(0);
});

test("says when the download fails", async () => {
  await openPage({ [documentRoute("GET", brief.id)]: { status: 500 } });

  await userEvent.click(
    screen.getByRole("button", { name: "Download Client brief.pdf" }),
  );

  expect(
    await screen.findByText("Couldn't download Client brief.pdf. Try again."),
  ).toBeInTheDocument();
  const row = screen.getByRole("listitem");
  expect(
    within(row).getByRole("button", { name: "Download Client brief.pdf" }),
  ).not.toHaveAttribute("aria-busy");
});
