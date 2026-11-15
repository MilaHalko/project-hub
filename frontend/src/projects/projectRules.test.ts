import { expect, test } from "vitest";
import { checkProject } from "./projectRules";

test("accepts a normal project", () => {
  expect(checkProject({ name: "Website redesign", description: "" })).toEqual(
    {},
  );
});

test("asks for a name when it is empty or blank", () => {
  expect(checkProject({ name: "", description: "" }).name).toBe(
    "Enter a project name.",
  );
  expect(checkProject({ name: "   ", description: "" }).name).toBe(
    "Enter a project name.",
  );
});

test("allows 100 characters plus surrounding spaces, not 101", () => {
  expect(
    checkProject({ name: ` ${"a".repeat(100)} `, description: "" }),
  ).toEqual({});
  expect(checkProject({ name: "a".repeat(101), description: "" }).name).toBe(
    "Use 100 characters or fewer.",
  );
});

test("rejects tabs and line breaks in the name", () => {
  const message = "Remove tabs and line breaks from the name.";
  expect(checkProject({ name: "a\tb", description: "" }).name).toBe(message);
  expect(checkProject({ name: "a\nb", description: "" }).name).toBe(message);
});

test("allows a 2000-character description, not 2001", () => {
  expect(checkProject({ name: "a", description: "d".repeat(2000) })).toEqual(
    {},
  );
  expect(
    checkProject({ name: "a", description: "d".repeat(2001) }).description,
  ).toBe("Use 2000 characters or fewer.");
});

test("counts an emoji as one character, like the server", () => {
  expect(checkProject({ name: "😀".repeat(100), description: "" })).toEqual({});
  expect(checkProject({ name: "😀".repeat(101), description: "" }).name).toBe(
    "Use 100 characters or fewer.",
  );
  expect(checkProject({ name: "a", description: "😀".repeat(2000) })).toEqual(
    {},
  );
  expect(
    checkProject({ name: "a", description: "😀".repeat(2001) }).description,
  ).toBe("Use 2000 characters or fewer.");
});
