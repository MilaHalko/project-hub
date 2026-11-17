import { expect, test } from "vitest";
import { formatMegabytes, usedText } from "./space";

const MB = 1_048_576;

test.each([
  [0, "0 MB"],
  [1, "less than 0.1 MB"],
  [Math.ceil(0.1 * MB) - 1, "less than 0.1 MB"],
  [Math.ceil(0.1 * MB), "0.1 MB"],
  [1.5 * MB, "1.5 MB"],
  [9.94 * MB, "9.9 MB"],
  [9.95 * MB, "10 MB"],
  [10 * MB, "10 MB"],
  [10.6 * MB, "11 MB"],
  [18 * MB, "18 MB"],
  [50 * MB, "50 MB"],
])("shows %i bytes as %s", (bytes, shown) => {
  expect(formatMegabytes(bytes)).toBe(shown);
});

test.each([
  [18 * MB, 50 * MB, "18 of 50 MB used"],
  [0, 50 * MB, "0 of 50 MB used"],
  [218, 50 * MB, "Less than 0.1 MB of 50 MB used"],
  [MB, 1.5 * MB, "1 of 1.5 MB used"],
  [60 * MB, 50 * MB, "60 of 50 MB used"],
  [49.6 * MB, 50 * MB, "49.6 of 50 MB used"],
  [49.95 * MB, 50 * MB, "49.9 of 50 MB used"],
  [2.96 * MB, 3 * MB, "2.9 of 3 MB used"],
  [50 * MB, 50 * MB, "50 of 50 MB used"],
])("says %i of %i bytes as %s", (used, limit, said) => {
  expect(usedText(used, limit)).toBe(said);
});
