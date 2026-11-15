import { expect, test } from "vitest";
import { checkLogin, checkNewPassword } from "./passwordRules";

const loginMessage = "Use 3–32 characters: letters, digits, _ . -";

test.each(["ab", "a".repeat(33), "mi la", "міла"])(
  "rejects the login %j",
  (login) => {
    expect(checkLogin(login)).toBe(loginMessage);
  },
);

test("accepts a login with letters, digits and _ . -", () => {
  expect(checkLogin("mila_1.x-")).toBeNull();
});

test("rejects a password that is too short or too long", () => {
  expect(checkNewPassword("short", "x")).toBe("Use 8–128 characters");
  expect(checkNewPassword("a".repeat(129), "x")).toBe("Use 8–128 characters");
});

test("rejects a password with non-English letters", () => {
  expect(checkNewPassword("пароль123", "x")).toBe(
    "Use only English letters, digits, keyboard symbols and spaces",
  );
});

test("rejects a password equal to the login", () => {
  expect(checkNewPassword("mila1234", "mila1234")).toBe(
    "Password must not equal the login",
  );
});

test("accepts a normal password", () => {
  expect(checkNewPassword("correct horse", "mila")).toBeNull();
});
