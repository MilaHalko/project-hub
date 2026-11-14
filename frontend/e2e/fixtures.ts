import AxeBuilder from "@axe-core/playwright";
import { expect, test as base, type Page } from "@playwright/test";

export const test = base.extend<{ problems: string[] }>({
  problems: [
    async ({ page, baseURL }, use) => {
      const problems: string[] = [];
      const ownOrigin = new URL(baseURL ?? "http://127.0.0.1:8080").origin;
      page.on("console", (message) => {
        if (message.type() === "error") {
          problems.push(`console error: ${message.text()}`);
        }
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
