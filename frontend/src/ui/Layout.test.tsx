import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { renderApp } from "../test/renderApp";

test("has a skip link to the content", async () => {
  renderApp("/");

  const skip = await screen.findByRole("link", { name: "Skip to content" });
  expect(skip).toHaveAttribute("href", "#main");
  expect(screen.getByRole("main")).toHaveAttribute("id", "main");

  const main = screen.getByRole("main");
  main.focus();
  expect(main).toHaveFocus();
});

test("marks the current page in the main navigation", async () => {
  renderApp("/");

  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { name: "Projects" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

test("opens and closes the menu", async () => {
  const user = userEvent.setup();
  renderApp("/");

  const menu = await screen.findByRole("button", { name: "Menu" });
  expect(menu).toHaveAttribute("aria-expanded", "false");

  await user.click(menu);
  expect(menu).toHaveAttribute("aria-expanded", "true");

  await user.keyboard("{Escape}");
  expect(menu).toHaveAttribute("aria-expanded", "false");
  expect(menu).toHaveFocus();
});

test("closes the menu after choosing a page", async () => {
  const user = userEvent.setup();
  renderApp("/");

  const menu = await screen.findByRole("button", { name: "Menu" });
  await user.click(menu);
  const nav = screen.getByRole("navigation", { name: "Main" });
  await user.click(within(nav).getByRole("link", { name: "Projects" }));

  expect(menu).toHaveAttribute("aria-expanded", "false");
});

test("closes the menu when the page changes", async () => {
  const user = userEvent.setup();
  renderApp("/no-such-page");

  const menu = await screen.findByRole("button", { name: "Menu" });
  await user.click(menu);
  expect(menu).toHaveAttribute("aria-expanded", "true");
  await user.click(screen.getByRole("link", { name: "Go to projects" }));

  expect(menu).toHaveAttribute("aria-expanded", "false");
});
