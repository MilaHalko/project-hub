import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import type { Document } from "../api/documents";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import {
  brief,
  documentRoute,
  infoRoute,
  listRoute,
  project,
  PROJECT_ID,
  projectLostAfterFirstLoad,
  siteMap,
} from "./testData";

const newVersion: Document = {
  ...brief,
  name: "brief v2.docx",
  content_type:
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  size: 1_153_434,
  updated_at: new Date().toISOString(),
};

async function openPage(routes: Parameters<typeof mockApi>[0]) {
  const fetchMock = mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [siteMap, brief] },
    ...routes,
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("Client brief.pdf");
  return fetchMock;
}

function replaces(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      url === `/api/document/${brief.id}` && init?.method === "PUT",
  );
}

const v2 = () => new File(["PK"], "brief v2.docx");

test("replaces a document and keeps its place in the list", async () => {
  const fetchMock = await openPage({
    [documentRoute("PUT", brief.id)]: { status: 200, body: newVersion },
  });
  const file = v2();
  const input = screen.getByLabelText("Replace Client brief.pdf");

  expect(input).not.toHaveAttribute("multiple");
  await userEvent.upload(input, file);

  expect(await screen.findByText("File replaced")).toBeInTheDocument();
  const rows = screen.getAllByRole("listitem");
  expect(rows[0]).toHaveTextContent("Site map.docx");
  expect(rows[1]).toHaveTextContent("brief v2.docx");
  expect(rows[1]).toHaveTextContent("1.1 MB");
  expect(rows[1]).toHaveTextContent("Updated just now by mila");
  const calls = replaces(fetchMock);
  expect(calls).toHaveLength(1);
  const body = calls[0]?.[1]?.body;
  expect(body instanceof FormData && body.get("file")).toBe(file);
  expect(screen.getByLabelText("Replace brief v2.docx")).toHaveFocus();
});

test("shows Replacing… instead of the actions while the file goes", async () => {
  await openPage({
    [documentRoute("PUT", brief.id)]: () => new Promise(() => {}),
  });

  await userEvent.upload(
    screen.getByLabelText("Replace Client brief.pdf"),
    v2(),
  );

  const row = screen.getAllByRole("listitem")[1];
  if (!row) throw new Error("No second row");
  expect(within(row).getByText("Replacing…")).toBeInTheDocument();
  expect(
    within(row).queryByRole("button", { name: /Download/ }),
  ).not.toBeInTheDocument();
});

test("refuses a file that is not pdf or docx without a request", async () => {
  const fetchMock = await openPage({});
  const user = userEvent.setup({ applyAccept: false });

  await user.upload(
    screen.getByLabelText("Replace Client brief.pdf"),
    new File(["hi"], "notes.txt"),
  );

  expect(
    await screen.findByText(
      "notes.txt: only pdf, docx, jpg and png documents are allowed",
    ),
  ).toBeInTheDocument();
  expect(replaces(fetchMock)).toHaveLength(0);
});

test("shows the API's message when it refuses the new file", async () => {
  await openPage({
    [documentRoute("PUT", brief.id)]: {
      status: 422,
      body: { detail: "brief v2.docx: content is not a valid docx" },
    },
  });

  await userEvent.upload(
    screen.getByLabelText("Replace Client brief.pdf"),
    v2(),
  );

  expect(
    await screen.findByText("brief v2.docx: content is not a valid docx"),
  ).toBeInTheDocument();
  expect(screen.getByText("Client brief.pdf")).toBeInTheDocument();
});

test("says when the document is gone and reloads the list", async () => {
  const fetchMock = await openPage({
    [documentRoute("PUT", brief.id)]: {
      status: 404,
      body: { detail: "Document not found" },
    },
  });

  await userEvent.upload(
    screen.getByLabelText("Replace Client brief.pdf"),
    v2(),
  );

  expect(
    await screen.findByText(
      "This document no longer exists. Someone may have deleted it.",
    ),
  ).toBeInTheDocument();
  await vi.waitFor(() => {
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => url === `/api/project/${PROJECT_ID}/documents`,
      ),
    ).toHaveLength(2);
  });
});

test("tells a removed member they lost access instead of blaming the document", async () => {
  await openPage({
    [infoRoute]: projectLostAfterFirstLoad(),
    [documentRoute("PUT", brief.id)]: {
      status: 404,
      body: { detail: "Document not found" },
    },
  });

  await userEvent.upload(
    screen.getByLabelText("Replace Client brief.pdf"),
    v2(),
  );

  expect(
    await screen.findByText("You no longer have access to this project."),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByText(
      "This document no longer exists. Someone may have deleted it.",
    ),
  ).not.toBeInTheDocument();
});

test("reaches the row's actions with Tab in the order they show", async () => {
  await openPage({});
  const row = screen.getAllByRole("listitem")[1];
  if (!row) throw new Error("No second row");
  within(row)
    .getByRole("button", { name: "Download Client brief.pdf" })
    .focus();

  await userEvent.tab();
  expect(screen.getByLabelText("Replace Client brief.pdf")).toHaveFocus();
  await userEvent.tab();
  expect(
    within(row).getByRole("button", { name: "Delete Client brief.pdf" }),
  ).toHaveFocus();
});
