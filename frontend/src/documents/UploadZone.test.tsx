import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Document } from "../api/documents";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import {
  brief,
  infoRoute,
  listRoute,
  project,
  PROJECT_ID,
  siteMap,
  uploadRoute,
} from "./testData";

const pdf = () => new File(["%PDF-1.4"], "Invoice March.pdf");
const docx = () => new File(["PK"], "Contract.docx");
const txt = () => new File(["hello"], "notes.txt");

const invoice: Document = {
  ...brief,
  id: "20000000-0000-4000-8000-000000000010",
  name: "Invoice March.pdf",
  size: 8,
};
const contract: Document = {
  ...siteMap,
  id: "20000000-0000-4000-8000-000000000011",
  name: "Contract.docx",
  size: 2,
};

function uploads(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      url === `/api/project/${PROJECT_ID}/documents` && init?.method === "POST",
  );
}

function sentFile(
  call: Parameters<typeof fetch> | undefined,
): FormDataEntryValue | null {
  const body = call?.[1]?.body;
  if (!(body instanceof FormData)) throw new Error("The body is not a form");
  return body.get("files");
}

function answers(...bodies: (Document | { status: number; detail: string })[]) {
  let index = 0;
  return () => {
    const next = bodies[index];
    index += 1;
    if (next === undefined) throw new Error("No more upload answers");
    return "status" in next
      ? { status: next.status, body: { detail: next.detail } }
      : { status: 201, body: [next] };
  };
}

async function openPage(routes: Parameters<typeof mockApi>[0]) {
  const fetchMock = mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [] },
    ...routes,
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("No documents yet");
  return fetchMock;
}

function zone(): HTMLElement {
  return screen.getByText(/Drop PDF or DOCX files here/);
}

function fileDrag(files: File[]) {
  return {
    dataTransfer: { files, types: files.length ? ["Files"] : ["text/plain"] },
  };
}

test("uploads a pdf chosen in the file picker", async () => {
  const fetchMock = await openPage({ [uploadRoute]: answers(invoice) });
  const file = pdf();

  await userEvent.upload(screen.getByLabelText("Choose files"), file);

  const list = await screen.findByRole("list", { name: /^Documents/ });
  expect(
    await within(list).findByText("Invoice March.pdf"),
  ).toBeInTheDocument();
  expect(await screen.findByText("File uploaded")).toBeInTheDocument();
  const calls = uploads(fetchMock);
  expect(calls).toHaveLength(1);
  expect(sentFile(calls[0])).toBe(file);
  expect(
    screen.getByRole("heading", { level: 2, name: /^Documents/ }),
  ).toHaveTextContent("Documents 1");
});

test("sends good files one by one and keeps a bad one in the browser", async () => {
  const fetchMock = await openPage({
    [uploadRoute]: answers(invoice, contract),
  });
  const user = userEvent.setup({ applyAccept: false });

  await user.upload(screen.getByLabelText("Choose files"), [
    pdf(),
    txt(),
    docx(),
  ]);

  expect(await screen.findByText("2 files uploaded")).toBeInTheDocument();
  expect(
    uploads(fetchMock).map((call) => (sentFile(call) as File).name),
  ).toEqual(["Invoice March.pdf", "Contract.docx"]);
  const pending = screen.getByRole("list", { name: "Uploads" });
  expect(
    within(pending).getByText(
      "notes.txt: only pdf and docx documents are allowed",
    ),
  ).toBeInTheDocument();
  await user.click(
    within(pending).getByRole("button", { name: "Dismiss notes.txt" }),
  );
  expect(
    screen.queryByRole("list", { name: "Uploads" }),
  ).not.toBeInTheDocument();
});

test("shows which file is uploading and which is waiting", async () => {
  await openPage({ [uploadRoute]: () => new Promise(() => {}) });

  await userEvent.upload(screen.getByLabelText("Choose files"), [
    pdf(),
    docx(),
  ]);

  const items = within(
    await screen.findByRole("list", { name: "Uploads" }),
  ).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("Invoice March.pdf");
  expect(items[0]).toHaveTextContent("Uploading…");
  expect(items[1]).toHaveTextContent("Contract.docx");
  expect(items[1]).toHaveTextContent("Waiting");
});

test("keeps a file the API refused with the API's message", async () => {
  await openPage({
    [uploadRoute]: answers({
      status: 422,
      detail: "Invoice March.pdf: content is not a valid pdf",
    }),
  });

  await userEvent.upload(screen.getByLabelText("Choose files"), pdf());

  const pending = await screen.findByRole("list", { name: "Uploads" });
  expect(
    await within(pending).findByText(
      "Invoice March.pdf: content is not a valid pdf",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("status", { name: "Upload messages" }),
  ).toHaveTextContent("Invoice March.pdf: content is not a valid pdf");
  expect(screen.queryByText(/uploaded$/)).not.toBeInTheDocument();
});

test("gives two files with the same name their own rows", async () => {
  await openPage({ [uploadRoute]: () => new Promise(() => {}) });

  await userEvent.upload(screen.getByLabelText("Choose files"), [pdf(), pdf()]);

  const items = within(
    await screen.findByRole("list", { name: "Uploads" }),
  ).getAllByRole("listitem");
  expect(items).toHaveLength(2);
  expect(items[0]).toHaveTextContent("Uploading…");
  expect(items[1]).toHaveTextContent("Waiting");
});

test("stops the queue when the session ends", async () => {
  const fetchMock = await openPage({
    [uploadRoute]: answers({ status: 401, detail: "Not authenticated" }),
  });

  await userEvent.upload(screen.getByLabelText("Choose files"), [
    pdf(),
    docx(),
  ]);

  expect(
    await screen.findByRole("heading", { level: 1, name: /log in/i }),
  ).toBeInTheDocument();
  expect(uploads(fetchMock)).toHaveLength(1);
});

test("uploads a file dropped on the zone", async () => {
  const fetchMock = await openPage({ [uploadRoute]: answers(invoice) });
  const file = pdf();

  fireEvent.drop(zone(), fileDrag([file]));

  expect(await screen.findByText("File uploaded")).toBeInTheDocument();
  expect(sentFile(uploads(fetchMock)[0])).toBe(file);
});

test("ignores a drop that carries no files", async () => {
  const fetchMock = await openPage({});

  fireEvent.drop(zone(), fileDrag([]));

  expect(uploads(fetchMock)).toHaveLength(0);
  expect(
    screen.queryByRole("list", { name: "Uploads" }),
  ).not.toBeInTheDocument();
});

test("invites the drop while files are over the zone", async () => {
  await openPage({});
  const target = zone();

  fireEvent.dragEnter(target, fileDrag([pdf()]));

  expect(screen.getByText("Drop to upload")).toBeInTheDocument();
  fireEvent.dragLeave(screen.getByText("Drop to upload"), fileDrag([pdf()]));
  expect(zone()).toBeInTheDocument();
});

test("keeps a file dropped beside the zone from leaving the app", async () => {
  await openPage({});

  const allowed = fireEvent.dragOver(document.body, fileDrag([pdf()]));
  const dropped = fireEvent.drop(document.body, fileDrag([pdf()]));

  expect(allowed).toBe(false);
  expect(dropped).toBe(false);
});
