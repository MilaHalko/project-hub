import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Document } from "../api/documents";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import {
  brief,
  documentRoute,
  infoRoute,
  listRoute,
  project,
  PROJECT_ID,
  uploadRoute,
} from "./testData";

const MB = 1_048_576;
const LIMIT_DETAIL =
  "Project storage limit reached: 49 MB of 50 MB used, this upload needs 3 MB";
const REFUSED =
  "Report.pdf: not enough space. 49 of 50 MB used, this file needs 3 MB. Delete documents to make room.";

function spaces(...used: number[]) {
  let index = 0;
  return () => {
    const next = used[Math.min(index, used.length - 1)] ?? 0;
    index += 1;
    const body: Project = {
      ...project,
      storage_used_bytes: next,
      storage_limit_bytes: 50 * MB,
    };
    return { status: 200, body };
  };
}

const notes: Document = {
  ...brief,
  id: "20000000-0000-4000-8000-000000000020",
  name: "Notes.docx",
  size: 2,
};

test("says why a file did not fit and uploads the rest of the batch", async () => {
  let call = 0;
  mockApi({
    [infoRoute]: spaces(49 * MB, 49 * MB + 2),
    [listRoute]: { status: 200, body: [] },
    [uploadRoute]: () => {
      call += 1;
      return call === 1
        ? { status: 413, body: { detail: LIMIT_DETAIL } }
        : { status: 201, body: [notes] };
    },
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("No documents yet");

  await userEvent.upload(screen.getByLabelText("Choose files"), [
    new File(["%PDF-"], "Report.pdf"),
    new File(["PK"], "Notes.docx"),
  ]);

  expect(await screen.findByText("File uploaded")).toBeInTheDocument();
  const pending = screen.getByRole("list", { name: "Uploads" });
  expect(within(pending).getByText(REFUSED)).toBeInTheDocument();
  expect(
    screen.getByRole("status", { name: "Upload messages" }),
  ).toHaveTextContent(REFUSED);
  expect(
    within(screen.getByRole("list", { name: /^Documents/ })).getByText(
      "Notes.docx",
    ),
  ).toBeInTheDocument();
});

test("reloads the used space after a file did not fit", async () => {
  mockApi({
    [infoRoute]: spaces(20 * MB, 50 * MB),
    [listRoute]: { status: 200, body: [] },
    [uploadRoute]: { status: 413, body: { detail: LIMIT_DETAIL } },
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("20 of 50 MB used");

  await userEvent.upload(
    screen.getByLabelText("Choose files"),
    new File(["%PDF-"], "Report.pdf"),
  );

  expect(await screen.findByText("Limit reached")).toBeInTheDocument();
  expect(screen.getByText("50 of 50 MB used")).toBeInTheDocument();
  expect(
    within(screen.getByRole("list", { name: "Uploads" })).getByText(REFUSED),
  ).toBeInTheDocument();
});

test("says why a replacement did not fit and reloads the used space", async () => {
  mockApi({
    [infoRoute]: spaces(20 * MB, 50 * MB),
    [listRoute]: { status: 200, body: [brief] },
    [documentRoute("PUT", brief.id)]: {
      status: 413,
      body: { detail: LIMIT_DETAIL },
    },
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("Client brief.pdf");
  expect(screen.getByText("20 of 50 MB used")).toBeInTheDocument();

  await userEvent.upload(
    screen.getByLabelText("Replace Client brief.pdf"),
    new File(["%PDF-"], "Report.pdf"),
  );

  expect(await screen.findByText(REFUSED)).toBeInTheDocument();
  expect(await screen.findByText("Limit reached")).toBeInTheDocument();
  expect(screen.getByText("Client brief.pdf")).toBeInTheDocument();
});
