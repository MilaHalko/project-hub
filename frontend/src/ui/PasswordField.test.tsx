import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { PasswordField } from "./PasswordField";

test("shows and hides the password", async () => {
  const user = userEvent.setup();
  render(<PasswordField label="Password" />);
  const input = screen.getByLabelText("Password");
  const toggle = screen.getByRole("button", { name: "Show password" });

  expect(input).toHaveAttribute("type", "password");
  expect(toggle).toHaveAttribute("aria-pressed", "false");
  expect(toggle).toHaveTextContent("Show");

  await user.click(toggle);
  expect(input).toHaveAttribute("type", "text");
  expect(toggle).toHaveAttribute("aria-pressed", "true");
  expect(toggle).toHaveTextContent("Show");

  await user.click(toggle);
  expect(input).toHaveAttribute("type", "password");
  expect(toggle).toHaveAttribute("aria-pressed", "false");
});
