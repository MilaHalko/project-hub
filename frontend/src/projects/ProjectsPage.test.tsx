import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { renderApp } from "../test/renderApp";

test("shows the projects banner", async () => {
  renderApp("/");

  expect(
    await screen.findByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Sign-in and the projects list come next."),
  ).toBeInTheDocument();
});
