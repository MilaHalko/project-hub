import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import {
  brief,
  infoRoute,
  listRoute,
  project,
  PROJECT_ID,
  siteMap,
} from "./testData";

afterEach(() => {
  vi.useRealTimers();
});

async function section(): Promise<HTMLElement> {
  const heading = await screen.findByRole("heading", {
    level: 2,
    name: /^Documents/,
  });
  const region = heading.closest("section");
  if (!region) throw new Error("Documents heading is outside a section");
  return region;
}

test("lists the project's documents in the API's order with sizes and dates", async () => {
  vi.useFakeTimers({
    shouldAdvanceTime: true,
    now: new Date(2026, 10, 15, 12),
  });
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [brief, siteMap] },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const documents = await section();
  expect(
    within(documents).getByRole("heading", { level: 2 }),
  ).toHaveTextContent("Documents 2");
  const rows = await within(documents).findAllByRole("listitem");
  expect(rows).toHaveLength(2);
  expect(rows[0]).toHaveTextContent("Client brief.pdf");
  expect(rows[0]).toHaveTextContent("PDF");
  expect(rows[0]).toHaveTextContent("2.4 MB");
  expect(rows[0]).toHaveTextContent("Updated yesterday by mila");
  expect(rows[1]).toHaveTextContent("Site map.docx");
  expect(rows[1]).toHaveTextContent("DOCX");
  expect(rows[1]).toHaveTextContent("820 KB");
  expect(rows[1]).toHaveTextContent("Added Nov 12 by sam");
});

test("names a deleted uploader", async () => {
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: {
      status: 200,
      body: [{ ...siteMap, uploaded_by: null }],
    },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const row = await within(await section()).findByRole("listitem");
  expect(row).toHaveTextContent("Added Nov 12 by a deleted account");
});

test("shows the exact time of the date on hover", async () => {
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [siteMap] },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const row = await within(await section()).findByRole("listitem");
  const time = row.querySelector("time");
  expect(time).toHaveAttribute("dateTime", siteMap.updated_at);
  expect(time?.getAttribute("title")).toMatch(/^Nov 12, 2026, \d\d:\d\d$/);
});

test("says when the project has no documents", async () => {
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [] },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const documents = await section();
  expect(
    await within(documents).findByText("No documents yet"),
  ).toBeInTheDocument();
  expect(
    within(documents).getByText("Upload the first one above."),
  ).toBeInTheDocument();
  expect(within(documents).queryByRole("listitem")).not.toBeInTheDocument();
});

test("shows a placeholder while the documents load", async () => {
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: () => new Promise(() => {}),
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const documents = await section();
  expect(
    within(documents).getByRole("status", { name: "Loading documents" }),
  ).toBeInTheDocument();
});

test("offers to try again when the list fails to load", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  let failing = true;
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: () =>
      failing ? { status: 500 } : { status: 200, body: [brief] },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  const documents = await section();
  await vi.advanceTimersByTimeAsync(2000);
  expect(
    within(documents).getByText("Couldn't load the documents."),
  ).toBeInTheDocument();
  failing = false;
  await user.click(
    within(documents).getByRole("button", { name: "Try again" }),
  );
  expect(
    await within(documents).findByText("Client brief.pdf"),
  ).toBeInTheDocument();
});

test("shows the same documents to a participant", async () => {
  mockApi({
    [infoRoute]: {
      status: 200,
      body: {
        ...project,
        my_role: "participant",
        owner: { id: "00000000-0000-4000-8000-000000000002", login: "sam" },
      },
    },
    [listRoute]: { status: 200, body: [brief] },
  });
  renderApp(`/projects/${PROJECT_ID}`);

  expect(
    await within(await section()).findByText("Client brief.pdf"),
  ).toBeInTheDocument();
});
