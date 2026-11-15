import { act, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { AppProviders } from "../AppProviders";
import type { Document } from "../api/documents";
import { setToken } from "../auth/tokenStore";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import { routes } from "../routes";
import {
  brief,
  infoRoute,
  listRoute,
  project,
  PROJECT_ID,
  uploadRoute,
} from "./testData";

const OTHER_ID = "10000000-0000-4000-8000-000000000009";

function later<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

test("still names a file that fails after the page was left", async () => {
  const first = later<{ status: number; body: Document[] }>();
  let call = 0;
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [] },
    [uploadRoute]: () => {
      call += 1;
      return call === 1
        ? first.promise
        : {
            status: 422,
            body: { detail: "Contract.docx: content is not a valid docx" },
          };
    },
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("No documents yet");

  await userEvent.upload(screen.getByLabelText("Choose files"), [
    new File(["%PDF-"], "Invoice.pdf"),
    new File(["PK"], "Contract.docx"),
  ]);
  await userEvent.click(
    within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole(
      "link",
      { name: "Projects" },
    ),
  );
  await screen.findByRole("heading", { level: 1, name: "Your projects" });
  first.resolve({ status: 201, body: [{ ...brief, name: "Invoice.pdf" }] });

  expect(
    await screen.findByText("Contract.docx: content is not a valid docx"),
  ).toBeInTheDocument();
});

test("sends a file to the project whose page it was chosen on", async () => {
  setToken("test-token");
  const fetchMock = mockApi({
    [infoRoute]: { status: 200, body: project },
    [`GET /api/project/${OTHER_ID}/info`]: {
      status: 200,
      body: { ...project, id: OTHER_ID, name: "Other project" },
    },
    [uploadRoute]: () => new Promise(() => {}),
    [`POST /api/project/${OTHER_ID}/documents`]: () => new Promise(() => {}),
  });
  const router = createMemoryRouter(routes, {
    initialEntries: [`/projects/${OTHER_ID}`],
  });
  render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  await screen.findByRole("heading", { level: 1, name: "Other project" });
  await act(() => router.navigate(`/projects/${PROJECT_ID}`));
  await screen.findByRole("heading", { level: 1, name: "Website redesign" });
  await screen.findByText("No documents yet");
  await userEvent.upload(
    screen.getByLabelText("Choose files"),
    new File(["%PDF-"], "For A.pdf"),
  );

  await act(() => router.navigate(`/projects/${OTHER_ID}`));
  await screen.findByRole("heading", { level: 1, name: "Other project" });
  expect(
    screen.queryByRole("list", { name: "Uploads" }),
  ).not.toBeInTheDocument();
  await userEvent.upload(
    screen.getByLabelText("Choose files"),
    new File(["%PDF-"], "For B.pdf"),
  );

  const posted = fetchMock.mock.calls
    .filter(([, init]) => init?.method === "POST")
    .map(([url, init]) => [
      url,
      ((init?.body as FormData).get("files") as File).name,
    ]);
  expect(posted).toEqual([
    [`/api/project/${PROJECT_ID}/documents`, "For A.pdf"],
    [`/api/project/${OTHER_ID}/documents`, "For B.pdf"],
  ]);
});

test("moves the focus to the next upload message after Dismiss", async () => {
  mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: [] },
  });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("No documents yet");
  const user = userEvent.setup({ applyAccept: false });
  await user.upload(screen.getByLabelText("Choose files"), [
    new File(["a"], "a.txt"),
    new File(["b"], "b.txt"),
  ]);

  await user.click(screen.getByRole("button", { name: "Dismiss a.txt" }));
  expect(screen.getByRole("button", { name: "Dismiss b.txt" })).toHaveFocus();

  await user.click(screen.getByRole("button", { name: "Dismiss b.txt" }));
  expect(screen.getByLabelText("Choose files")).toHaveFocus();
});
