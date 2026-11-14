import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
} from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { LoaderBar } from "./LoaderBar";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<string>((done) => {
    resolve = () => {
      done("ok");
    };
  });
  return { promise, resolve };
}

function renderWithClient(children: React.ReactNode) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <LoaderBar />
      {children}
    </QueryClientProvider>,
  );
}

function QueryProbe({ promise }: { promise: Promise<string> }) {
  useQuery({ queryKey: ["probe"], queryFn: () => promise });
  return null;
}

function MutationProbe({ promise }: { promise: Promise<string> }) {
  const mutation = useMutation({ mutationFn: () => promise });
  return (
    <button
      type="button"
      onClick={() => {
        mutation.mutate();
      }}
    >
      Save
    </button>
  );
}

test("shows while a query runs and hides after", async () => {
  const { promise, resolve } = deferred();
  renderWithClient(<QueryProbe promise={promise} />);

  expect(
    await screen.findByRole("progressbar", { name: "Loading" }),
  ).toBeInTheDocument();

  resolve();

  await waitFor(() => {
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
});

test("shows while a mutation runs", async () => {
  const { promise, resolve } = deferred();
  renderWithClient(<MutationProbe promise={promise} />);

  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(
    await screen.findByRole("progressbar", { name: "Loading" }),
  ).toBeInTheDocument();

  resolve();

  await waitFor(() => {
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
});

test("is absent when nothing runs", () => {
  renderWithClient(null);

  expect(screen.queryByRole("progressbar")).toBeNull();
});
