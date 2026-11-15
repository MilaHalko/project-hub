import { expect, test } from "vitest";
import { ApiError, fieldErrors, messageFor } from "./errors";

test("puts a field error next to its field", () => {
  const error = new ApiError(422, [
    {
      type: "string_too_short",
      loc: ["body", "login"],
      msg: "String should have at least 3 characters",
    },
  ]);

  expect(fieldErrors(error)).toEqual({
    fields: { login: "String should have at least 3 characters" },
    form: null,
  });
});

test("turns a body-level error into a form message without the prefix", () => {
  const error = new ApiError(422, [
    {
      type: "value_error",
      loc: ["body"],
      msg: "Value error, Passwords do not match",
    },
  ]);

  expect(fieldErrors(error)).toEqual({
    fields: {},
    form: "Passwords do not match",
  });
});

test("turns a string detail into a form message", () => {
  const error = new ApiError(422, "Password must not equal the login");

  expect(fieldErrors(error)).toEqual({
    fields: {},
    form: "Password must not equal the login",
  });
});

test.each([
  [new ApiError(0, null), "Something went wrong. Try again."],
  [new ApiError(500, null), "Something went wrong. Try again."],
  [new ApiError(403, "Forbidden"), "You don't have permission to do this."],
  [new Error("boom"), "Something went wrong. Try again."],
])("gives %o the message %j", (error, message) => {
  expect(messageFor(error)).toBe(message);
});
