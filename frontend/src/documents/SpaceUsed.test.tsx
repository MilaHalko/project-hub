import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import type { Project } from "../api/projects";
import { mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import { infoRoute, project, PROJECT_ID } from "./testData";

const MB = 1_048_576;

async function openPage(body: Project) {
  mockApi({ [infoRoute]: { status: 200, body } });
  renderApp(`/projects/${PROJECT_ID}`);
  await screen.findByText("No documents yet");
}

function withSpace(used: number, limit = 50 * MB): Project {
  return { ...project, storage_used_bytes: used, storage_limit_bytes: limit };
}

test("shows how much of the project's space is used", async () => {
  await openPage(withSpace(18 * MB));

  expect(screen.getByText("18 of 50 MB used")).toBeInTheDocument();
  const meter = screen.getByRole("meter", { name: "Space used" });
  expect(meter).toHaveAttribute("aria-valuemin", "0");
  expect(meter).toHaveAttribute("aria-valuemax", String(50 * MB));
  expect(meter).toHaveAttribute("aria-valuenow", String(18 * MB));
  expect(meter).toHaveAttribute("aria-valuetext", "18 of 50 MB used");
  expect(meter.className).not.toMatch(/warn/);
  expect(screen.queryByText(/Limit reached/)).not.toBeInTheDocument();
  expect(screen.getByText("PDF or DOCX, up to 10 MB each")).toBeInTheDocument();
});

test("shows the same space to a participant", async () => {
  await openPage({ ...withSpace(3 * MB), my_role: "participant" });

  expect(screen.getByRole("meter", { name: "Space used" })).toHaveAttribute(
    "aria-valuetext",
    "3 of 50 MB used",
  );
});

test("shows no space at all when the API does not send it", async () => {
  await openPage(project);

  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  expect(screen.queryByText(/ used$/)).not.toBeInTheDocument();
});

test("warns from 80 % of the limit", async () => {
  await openPage(withSpace(40 * MB));

  const meter = screen.getByRole("meter", { name: "Space used" });
  expect(meter.className).toMatch(/warn/);
  expect(screen.getByText("40 of 50 MB used")).toBeInTheDocument();
  expect(screen.queryByText(/Limit reached/)).not.toBeInTheDocument();
});

test("never shows the limit as used just below it", async () => {
  await openPage(withSpace(49.95 * MB));

  expect(screen.getByText("49.9 of 50 MB used")).toBeInTheDocument();
  expect(screen.getByRole("meter", { name: "Space used" })).toHaveAttribute(
    "aria-valuetext",
    "49.9 of 50 MB used",
  );
  expect(screen.queryByText(/Limit reached/)).not.toBeInTheDocument();
});

test("says the limit is reached and how to make room", async () => {
  await openPage(withSpace(50 * MB));

  const meter = screen.getByRole("meter", { name: "Space used" });
  expect(meter.className).toMatch(/warn/);
  expect(meter).toHaveAttribute(
    "aria-valuetext",
    "50 of 50 MB used. Limit reached",
  );
  expect(screen.getByText("Limit reached")).toBeInTheDocument();
  expect(
    screen.getByText("Delete documents to make room."),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("PDF or DOCX, up to 10 MB each"),
  ).not.toBeInTheDocument();
});

test("shows the real number with a full bar when the limit was lowered", async () => {
  await openPage(withSpace(60 * MB));

  expect(screen.getByText("60 of 50 MB used")).toBeInTheDocument();
  const meter = screen.getByRole("meter", { name: "Space used" });
  expect(meter).toHaveAttribute("aria-valuenow", String(50 * MB));
  expect(meter).toHaveAttribute(
    "aria-valuetext",
    "60 of 50 MB used. Limit reached",
  );
});
