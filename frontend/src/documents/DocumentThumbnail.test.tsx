import { act, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import {
  brief,
  infoRoute,
  listRoute,
  photo,
  previewRoute,
  project,
  PROJECT_ID,
} from "./testData";

const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:preview");
const revokeObjectURL = vi.fn();
const picture = new Blob(["jpeg bytes"], { type: "image/jpeg" });

beforeEach(() => {
  Object.assign(URL, { createObjectURL, revokeObjectURL });
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  createObjectURL.mockClear();
  revokeObjectURL.mockClear();
  vi.useRealTimers();
});

function openPage(documents: unknown[], routes: Parameters<typeof mockApi>[0]) {
  const fetchMock = mockApi({
    [infoRoute]: { status: 200, body: project },
    [listRoute]: { status: 200, body: documents },
    ...routes,
  });
  const view = renderApp(`/projects/${PROJECT_ID}`);
  return { fetchMock, view };
}

function previewCalls(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.filter(([url]) => url === previewUrl);
}

const previewUrl = `/api/document/${photo.id}/preview`;

test("shows the picture instead of the type badge once the preview exists", async () => {
  openPage([photo], {
    [previewRoute(photo.id)]: { status: 200, body: picture },
  });

  const image = await screen.findByRole("img", {
    name: "Preview of Mood board.png",
  });
  expect(image).toHaveAttribute("src", "blob:preview");
  expect(screen.queryByText("PNG")).not.toBeInTheDocument();
});

test("keeps the type badge and retries while the preview is not ready", async () => {
  let answers = 0;
  const { fetchMock } = openPage([photo], {
    [previewRoute(photo.id)]: () => {
      answers += 1;
      return answers < 3
        ? { status: 404, body: { detail: "The preview is not ready yet." } }
        : { status: 200, body: picture };
    },
  });

  expect(await screen.findByText("PNG")).toBeInTheDocument();
  await act(() => vi.advanceTimersByTimeAsync(10_000));

  expect(
    await screen.findByRole("img", { name: "Preview of Mood board.png" }),
  ).toBeInTheDocument();
  expect(previewCalls(fetchMock)).toHaveLength(3);
});

test("gives up quietly when the preview never appears", async () => {
  const { fetchMock } = openPage([photo], {
    [previewRoute(photo.id)]: { status: 404, body: { detail: "not ready" } },
  });
  expect(await screen.findByText("PNG")).toBeInTheDocument();

  await act(() => vi.advanceTimersByTimeAsync(60_000));

  expect(screen.getByText("PNG")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.getByRole("alert")).toBeEmptyDOMElement();
  expect(previewCalls(fetchMock).length).toBeGreaterThan(1);
  expect(previewCalls(fetchMock).length).toBeLessThanOrEqual(6);
});

test("releases the picture when the page is left", async () => {
  const { view } = openPage([photo], {
    [previewRoute(photo.id)]: { status: 200, body: picture },
  });
  await screen.findByRole("img", { name: "Preview of Mood board.png" });

  view.unmount();

  expect(revokeObjectURL).toHaveBeenCalledWith("blob:preview");
});

test("asks for no preview of a pdf", async () => {
  const { fetchMock } = openPage([brief], {});
  await screen.findByText("Client brief.pdf");

  expect(screen.getByText("PDF")).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([url]) => typeof url === "string" && url.includes("preview"),
    ),
  ).toBe(false);
});
