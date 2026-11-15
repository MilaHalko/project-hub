import { expect, test } from "vitest";
import { defaultAvatarName } from "./defaultAvatarName";

function idNumber(n: number): string {
  return `00000000-0000-4000-8000-0000000000${String(n).padStart(2, "0")}`;
}

test("gives the same avatar for the same id", () => {
  const id = idNumber(1);
  expect(defaultAvatarName(id)).toBe(defaultAvatarName(id));
});

test("spreads different ids over several avatars", () => {
  const names = new Set(
    Array.from({ length: 20 }, (_, n) => defaultAvatarName(idNumber(n))),
  );
  expect(names.size).toBeGreaterThanOrEqual(5);
});

test("keeps the avatar every existing user already has", () => {
  expect(defaultAvatarName(idNumber(1))).toBe("wave");
  expect(defaultAvatarName("a3f1c2d4-5b6e-4f70-8a9b-0c1d2e3f4a5b")).toBe("arc");
});
