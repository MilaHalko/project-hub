import { expect, test } from "vitest";
import { fileKind, formatSize } from "./fileRules";

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
])("knows the kind of %s", (name, kind) => {
  expect(fileKind(name)).toBe(kind);
});
