import { expect, test } from "vitest";
import { safeNext } from "./safeNext";

test("keeps a path inside the app", () => {
  expect(safeNext("/profile?x=1")).toBe("/profile?x=1");
});

test.each([
  null,
  "",
  "//evil.example",
  "/\\evil",
  "https://evil.example",
  "profile",
  "/login",
  "/login?next=/x",
  "/register",
])("sends %j to the projects page", (next) => {
  expect(safeNext(next)).toBe("/");
});
