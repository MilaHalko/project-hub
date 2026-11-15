import { expect, test } from "vitest";
import { formatDate, formatUpdated } from "./time";

const now = new Date("2026-11-15T12:00:00");

function before(milliseconds: number): string {
  return new Date(now.getTime() - milliseconds).toISOString();
}

function local(dateTime: string): string {
  return new Date(dateTime).toISOString();
}

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;

test.each([
  ["30 seconds ago", before(30 * SECOND), "just now"],
  ["1 minute ago", before(MINUTE), "1 minute ago"],
  ["5 minutes ago", before(5 * MINUTE), "5 minutes ago"],
  ["1 hour ago", before(HOUR), "1 hour ago"],
  ["2 hours ago", before(2 * HOUR), "2 hours ago"],
  ["the day before", local("2026-11-14T09:00:00"), "yesterday"],
  ["earlier this year", local("2026-11-12T10:00:00"), "Nov 12"],
  ["another year", local("2025-11-12T10:00:00"), "Nov 12, 2025"],
  ["the future", before(-5 * MINUTE), "just now"],
])("shows an update from %s as %j", (_, iso, expected) => {
  expect(formatUpdated(iso, now)).toBe(expected);
});

test("formats a date with the year", () => {
  expect(formatDate("2026-11-12T10:00:00Z")).toBe("Nov 12, 2026");
});
