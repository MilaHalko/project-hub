import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test as base,
  type ConsoleMessage,
  type Page,
} from "@playwright/test";

const FAILED_RESOURCE =
  /^Failed to load resource: the server responded with a status of (\d+)/;

function isExpectedApiError(message: ConsoleMessage, statuses: number[]) {
  const status = FAILED_RESOURCE.exec(message.text())?.[1];
  if (status === undefined || !statuses.includes(Number(status))) return false;
  return new URL(message.location().url).pathname.startsWith("/api/");
}

export const test = base.extend<{
  expectedApiStatuses: number[];
  problems: string[];
}>({
  expectedApiStatuses: [[], { option: true }],
  problems: [
    async ({ page, baseURL, expectedApiStatuses }, use) => {
      const problems: string[] = [];
      const ownOrigin = new URL(baseURL ?? "http://127.0.0.1:8080").origin;
      page.on("console", (message) => {
        if (message.type() !== "error") return;
        if (isExpectedApiError(message, expectedApiStatuses)) return;
        problems.push(`console error: ${message.text()}`);
      });
      page.on("pageerror", (error) => {
        problems.push(`page error: ${error.message}`);
      });
      page.on("request", (request) => {
        const url = new URL(request.url());
        if (url.protocol === "data:" || url.protocol === "blob:") return;
        if (url.origin !== ownOrigin) {
          problems.push(`request to another origin: ${request.url()}`);
        }
      });
      await use(problems);
      expect(problems).toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

export async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}
