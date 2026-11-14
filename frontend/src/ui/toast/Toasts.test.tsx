import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ToastProvider } from "./ToastProvider";
import { useToast } from "./useToast";

function Probe() {
  const toast = useToast();
  return (
    <>
      <button
        type="button"
        onClick={() => {
          toast.success("Project created");
        }}
      >
        Succeed
      </button>
      <button
        type="button"
        onClick={() => {
          toast.error("Could not save the project");
        }}
      >
        Fail
      </button>
    </>
  );
}

function renderProbe() {
  return render(
    <ToastProvider>
      <Probe />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

test("shows a success toast and hides it after 5 seconds", () => {
  renderProbe();

  fireEvent.click(screen.getByRole("button", { name: "Succeed" }));

  expect(
    within(screen.getByRole("status")).getByText("Project created"),
  ).toBeInTheDocument();

  advance(4999);
  expect(screen.getByText("Project created")).toBeInTheDocument();

  advance(1);
  expect(screen.queryByText("Project created")).toBeNull();
});

test("keeps an error toast until dismissed", () => {
  renderProbe();

  fireEvent.click(screen.getByRole("button", { name: "Fail" }));

  const alert = screen.getByRole("alert");
  expect(within(alert).getByText("Could not save the project")).toBeVisible();

  advance(60000);
  expect(
    within(alert).getByText("Could not save the project"),
  ).toBeInTheDocument();

  fireEvent.click(
    within(alert).getByRole("button", { name: "Dismiss notification" }),
  );
  expect(screen.queryByText("Could not save the project")).toBeNull();
});

test("stacks several toasts", () => {
  renderProbe();

  fireEvent.click(screen.getByRole("button", { name: "Succeed" }));
  fireEvent.click(screen.getByRole("button", { name: "Succeed" }));
  fireEvent.click(screen.getByRole("button", { name: "Fail" }));

  expect(
    within(screen.getByRole("status")).getAllByText("Project created"),
  ).toHaveLength(2);
  expect(
    within(screen.getByRole("alert")).getByText("Could not save the project"),
  ).toBeInTheDocument();
  expect(
    screen.getAllByRole("button", { name: "Dismiss notification" }),
  ).toHaveLength(3);
});

test("useToast outside the provider throws", () => {
  const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);

  expect(() => render(<Probe />)).toThrow(/ToastProvider/);

  spy.mockRestore();
});
