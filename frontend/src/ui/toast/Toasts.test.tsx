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

test("keeps a success toast while the pointer is over it", () => {
  renderProbe();
  fireEvent.click(screen.getByRole("button", { name: "Succeed" }));
  const toast = screen.getByText("Project created").closest("div");
  if (toast === null) throw new Error("toast not found");

  advance(3000);
  fireEvent.mouseEnter(toast);
  advance(10000);
  expect(screen.getByText("Project created")).toBeInTheDocument();

  fireEvent.mouseLeave(toast);
  advance(4999);
  expect(screen.getByText("Project created")).toBeInTheDocument();
  advance(1);
  expect(screen.queryByText("Project created")).toBeNull();
});

test("keeps a success toast while focus is inside it", () => {
  renderProbe();
  fireEvent.click(screen.getByRole("button", { name: "Succeed" }));
  const dismiss = screen.getByRole("button", { name: "Dismiss notification" });

  act(() => {
    dismiss.focus();
  });
  advance(10000);
  expect(screen.getByText("Project created")).toBeInTheDocument();

  act(() => {
    dismiss.blur();
  });
  advance(4999);
  expect(screen.getByText("Project created")).toBeInTheDocument();
  advance(1);
  expect(screen.queryByText("Project created")).toBeNull();
});

test("keeps the timer paused until both the pointer and focus have left", () => {
  renderProbe();
  fireEvent.click(screen.getByRole("button", { name: "Succeed" }));
  const dismiss = screen.getByRole("button", { name: "Dismiss notification" });
  const toast = screen.getByText("Project created").closest("div");
  if (toast === null) throw new Error("toast not found");

  fireEvent.mouseEnter(toast);
  act(() => {
    dismiss.focus();
  });
  fireEvent.mouseLeave(toast);
  advance(10000);
  expect(screen.getByText("Project created")).toBeInTheDocument();

  act(() => {
    dismiss.blur();
  });
  advance(5000);
  expect(screen.queryByText("Project created")).toBeNull();
});

test("after a keyboard dismiss focus goes to the next toast's Dismiss button", () => {
  renderProbe();
  fireEvent.click(screen.getByRole("button", { name: "Succeed" }));
  fireEvent.click(screen.getByRole("button", { name: "Succeed" }));
  const [first, second] = screen.getAllByRole("button", {
    name: "Dismiss notification",
  });
  if (first === undefined || second === undefined) throw new Error("no toasts");

  act(() => {
    first.focus();
  });
  fireEvent.click(first);

  expect(second).toHaveFocus();
});

test("after dismissing the last toast focus returns to where it was", () => {
  renderProbe();
  const fail = screen.getByRole("button", { name: "Fail" });
  act(() => {
    fail.focus();
  });
  fireEvent.click(fail);
  const dismiss = screen.getByRole("button", { name: "Dismiss notification" });
  act(() => {
    dismiss.focus();
  });

  fireEvent.click(dismiss);

  expect(fail).toHaveFocus();
});

test("after dismissing the last toast focus falls back to main", () => {
  render(
    <ToastProvider>
      <main id="main" tabIndex={-1}>
        <Probe />
      </main>
    </ToastProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Fail" }));
  const dismiss = screen.getByRole("button", { name: "Dismiss notification" });
  act(() => {
    dismiss.focus();
  });

  fireEvent.click(dismiss);

  expect(screen.getByRole("main")).toHaveFocus();
});

test("announces only new toasts", () => {
  renderProbe();
  for (const region of [
    screen.getByRole("status"),
    screen.getByRole("alert"),
  ]) {
    expect(region).toHaveAttribute("aria-atomic", "false");
    expect(region).toHaveAttribute("aria-relevant", "additions");
  }
});
