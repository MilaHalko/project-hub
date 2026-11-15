import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { renderApp } from "../test/renderApp";

test("shows not found for an unknown path", async () => {
  const user = userEvent.setup();
  renderApp("/no-such-page");

  expect(
    await screen.findByRole("heading", { level: 1, name: "Page not found" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "This page does not exist. Check the address or go back to your projects.",
    ),
  ).toBeInTheDocument();
  const link = screen.getByRole("link", { name: "Go to projects" });
  expect(link).toHaveAttribute("href", "/projects");

  await user.click(link);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
});
