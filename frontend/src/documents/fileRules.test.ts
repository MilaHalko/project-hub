import { expect, test } from "vitest";
import { ApiError } from "../api/errors";
import {
  checkFile,
  fileKind,
  formatSize,
  MAX_FILE_BYTES,
  uploadErrorMessage,
} from "./fileRules";

test.each([
  [0, "0 B"],
  [512, "512 B"],
  [1023, "1023 B"],
  [1024, "1 KB"],
  [839_680, "820 KB"],
  [1_048_576, "1 MB"],
  [2_516_582, "2.4 MB"],
  [10_485_760, "10 MB"],
])("formats %i bytes as %s", (bytes, text) => {
  expect(formatSize(bytes)).toBe(text);
});

test.each([
  ["Brief.pdf", "pdf"],
  ["A.PDF", "pdf"],
  ["site map.docx", "docx"],
  ["Notes.DocX", "docx"],
  ["notes.txt", null],
  ["pdf", null],
  ["archive.pdf.zip", null],
  ["old.doc", null],
  ["photo.jpg", "jpg"],
  ["Photo.JPEG", "jpg"],
  ["scan.png", "png"],
  ["scan.PNG", "png"],
  ["photo.jpg.exe", null],
  ["image.gif", null],
])("knows the kind of %s", (name, kind) => {
  expect(fileKind(name)).toBe(kind);
});

function fileOf(name: string, size: number): File {
  const file = new File([], name);
  Object.defineProperty(file, "size", { value: size });
  return file;
}

test.each([
  [
    "notes.txt",
    10,
    "notes.txt: only pdf, docx, jpg and png documents are allowed",
  ],
  ["a.pdf", 0, "a.pdf: file is empty"],
  ["a.pdf", MAX_FILE_BYTES + 1, "a.pdf: file is larger than 10 MB"],
  [
    "big.txt",
    MAX_FILE_BYTES + 1,
    "big.txt: only pdf, docx, jpg and png documents are allowed",
  ],
  ["a.pdf", MAX_FILE_BYTES, null],
  ["b.DOCX", 1, null],
  ["c.jpeg", 1, null],
  ["d.png", MAX_FILE_BYTES, null],
  ["e.jpg", MAX_FILE_BYTES + 1, "e.jpg: file is larger than 10 MB"],
])("checks %s of %i bytes before sending", (name, size, message) => {
  expect(checkFile(fileOf(name, size))).toBe(message);
});

test("shows the API's own words for a refused file", () => {
  expect(
    uploadErrorMessage(
      new ApiError(422, "a.pdf: content is not a valid pdf"),
      "a.pdf",
    ),
  ).toBe("a.pdf: content is not a valid pdf");
});

test("says when the file storage is down", () => {
  expect(
    uploadErrorMessage(
      new ApiError(503, "File storage is unavailable"),
      "a.pdf",
    ),
  ).toBe("File storage is unavailable. Try again later.");
});

test("says when the network is down", () => {
  expect(uploadErrorMessage(new ApiError(0, null), "a.pdf")).toBe(
    "a.pdf: couldn't upload. Check your connection and try again.",
  );
});

test("falls back to a plain message without a detail", () => {
  expect(uploadErrorMessage(new ApiError(500, null), "a.pdf")).toBe(
    "a.pdf: couldn't upload. Try again.",
  );
});

test.each([
  [
    "Project storage limit reached: 49 MB of 50 MB used, this upload needs 3 MB",
    "Report.pdf: not enough space. 49 of 50 MB used, this file needs 3 MB. Delete documents to make room.",
  ],
  [
    "Project storage limit reached: 2097370 bytes of 3 MB used, this upload needs 1572864 bytes",
    "Report.pdf: not enough space. 2 of 3 MB used, this file needs 1.5 MB. Delete documents to make room.",
  ],
  [
    "Project storage limit reached: 218 bytes of 3 MB used, this upload needs 3 MB",
    "Report.pdf: not enough space. Less than 0.1 MB of 3 MB used, this file needs 3 MB. Delete documents to make room.",
  ],
  [
    "Project storage limit reached: 52376371 bytes of 50 MB used, this upload needs 3 MB",
    "Report.pdf: not enough space. 49.9 of 50 MB used, this file needs 3 MB. Delete documents to make room.",
  ],
  [
    "Project storage limit reached: somewhere around half",
    "Report.pdf: not enough space. Delete documents to make room.",
  ],
])("says why %j did not fit", (detail, message) => {
  expect(uploadErrorMessage(new ApiError(413, detail), "Report.pdf")).toBe(
    message,
  );
});

test("keeps a 413 detail that only starts like the limit message", () => {
  expect(
    uploadErrorMessage(
      new ApiError(413, "Project storage limit reached"),
      "Report.pdf",
    ),
  ).toBe("Project storage limit reached");
});

test("keeps the API's message for a file over 10 MB", () => {
  expect(
    uploadErrorMessage(
      new ApiError(413, "Scan.pdf: file is larger than 10 MB"),
      "Scan.pdf",
    ),
  ).toBe("Scan.pdf: file is larger than 10 MB");
});
