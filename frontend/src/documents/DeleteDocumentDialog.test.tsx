import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
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

async function openPage(routes: Parameters<typeof mockApi>[0]) {
  const fetchMock = mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [brief, siteMap] },
    ...routes,
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("Client brief.pdf");
  return fetchMock;
}

function deletes(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      url === `/api/document/${brief.id}` && init?.method === "DELETE",
  );
}

async function openDialog() {
  await userEvent.click(
    screen.getByRole("button", { name: "Delete Client brief.pdf" }),
  );
  return screen.getByRole("alertdialog", { name: "Delete this document?" });
}

test("asks before deleting and names the file", async () => {
  await openPage({});

  const dialog = await openDialog();

  expect(dialog).toHaveAccessibleDescription(
    "This deletes Client brief.pdf for everyone in the project. You can't undo this.",
  );
});

test("keeps the document on Cancel", async () => {
  const fetchMock = await openPage({});
  const dialog = await openDialog();

  await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

  expect(
    screen.queryByRole("alertdialog", { name: "Delete this document?" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Client brief.pdf")).toBeInTheDocument();
  expect(deletes(fetchMock)).toHaveLength(0);
});

test("deletes once even on a double click", async () => {
  const fetchMock = await openPage({
    [documentRoute("DELETE", brief.id)]: { status: 204 },
  });
  const dialog = await openDialog();

  await userEvent.dblClick(
    within(dialog).getByRole("button", { name: "Delete document" }),
  );

  expect(await screen.findByText("Document deleted")).toBeInTheDocument();
  expect(deletes(fetchMock)).toHaveLength(1);
  expect(screen.queryByText("Client brief.pdf")).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", { level: 2, name: /^Documents/ }),
  ).toHaveTextContent("Documents 1");
});

test("removes a document someone already deleted", async () => {
  await openPage({
    [documentRoute("DELETE", brief.id)]: {
      status: 404,
      body: { detail: "Document not found" },
    },
  });
  const dialog = await openDialog();

  await userEvent.click(
    within(dialog).getByRole("button", { name: "Delete document" }),
  );

  expect(
    await screen.findByText(
      "This document no longer exists. Someone may have deleted it.",
    ),
  ).toBeInTheDocument();
  expect(screen.queryByText("Client brief.pdf")).not.toBeInTheDocument();
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});

test("tells a removed member they lost access instead of blaming the document", async () => {
  await openPage({
    [infoRoute]: projectLostAfterFirstLoad(),
    [documentRoute("DELETE", brief.id)]: {
      status: 404,
      body: { detail: "Document not found" },
    },
  });
  const dialog = await openDialog();

  await userEvent.click(
    within(dialog).getByRole("button", { name: "Delete document" }),
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

test("keeps the dialog open when the project can't be checked after a 404", async () => {
  let loads = 0;
  await openPage({
    [infoRoute]: () => {
      loads += 1;
      return loads === 1 ? { status: 200, body: project } : { status: 500 };
    },
    [documentRoute("DELETE", brief.id)]: {
      status: 404,
      body: { detail: "Document not found" },
    },
  });
  const dialog = await openDialog();

  await userEvent.click(
    within(dialog).getByRole("button", { name: "Delete document" }),
  );

  expect(
    await within(dialog).findByText("Couldn't delete the document. Try again."),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Download Client brief.pdf" }),
  ).toBeInTheDocument();
});

test("keeps the dialog open with a message when the delete fails", async () => {
  await openPage({ [documentRoute("DELETE", brief.id)]: { status: 500 } });
  const dialog = await openDialog();

  await userEvent.click(
    within(dialog).getByRole("button", { name: "Delete document" }),
  );

  expect(
    await within(dialog).findByText("Couldn't delete the document. Try again."),
  ).toBeInTheDocument();
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
});

test("keeps the dialog open on Escape while the delete runs", async () => {
  await openPage({
    [documentRoute("DELETE", brief.id)]: () => new Promise(() => {}),
  });
  const dialog = await openDialog();

  await userEvent.click(
    within(dialog).getByRole("button", { name: "Delete document" }),
  );
  fireEvent(dialog, new Event("cancel", { cancelable: true }));

  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
});

async function deleteByName(name: string) {
  await userEvent.click(screen.getByRole("button", { name: `Delete ${name}` }));
  await userEvent.click(
    within(screen.getByRole("alertdialog")).getByRole("button", {
      name: "Delete document",
    }),
  );
  await waitFor(() => {
    expect(
      screen.queryByRole("button", { name: `Delete ${name}` }),
    ).not.toBeInTheDocument();
  });
}

test("moves the focus to the next document after a delete", async () => {
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [brief, siteMap] },
    [documentRoute("DELETE", brief.id)]: { status: 204 },
    [documentRoute("DELETE", siteMap.id)]: { status: 204 },
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("Client brief.pdf");

  await deleteByName("Client brief.pdf");
  expect(
    screen.getByRole("button", { name: "Download Site map.docx" }),
  ).toHaveFocus();

  await deleteByName("Site map.docx");
  expect(screen.getByLabelText("Choose files")).toHaveFocus();
});
