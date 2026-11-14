import { expect, test, type APIResponse } from "@playwright/test";

const contentSecurityPolicy =
  "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'";

function expectSecurityHeaders(response: APIResponse) {
  const headers = response.headers();
  expect(headers["content-security-policy"]).toBe(contentSecurityPolicy);
  expect(headers["referrer-policy"]).toBe("no-referrer");
  expect(headers["x-content-type-options"]).toBe("nosniff");
}

for (const path of ["/", "/projects/7", "/index.html"]) {
  test(`serves the app at ${path} without caching it`, async ({ request }) => {
    const response = await request.get(path);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("text/html");
    expect(response.headers()["cache-control"]).toBe("no-cache");
    expect(await response.text()).toContain('<div id="root">');
    expectSecurityHeaders(response);
  });
}

test("caches the hashed bundles for a year", async ({ request }) => {
  const html = await (await request.get("/")).text();
  const script = /src="(\/assets\/[^"]+\.js)"/.exec(html)?.[1];
  if (!script) throw new Error("index.html names no bundle under /assets/");
  const response = await request.get(script);
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("javascript");
  expect(response.headers()["cache-control"]).toBe(
    "public, max-age=31536000, immutable",
  );
  expectSecurityHeaders(response);
});

test("keeps files outside /assets/ fresh", async ({ request }) => {
  const response = await request.get("/favicon.svg");
  expect(response.status()).toBe(200);
  expect(response.headers()["cache-control"]).toBe("no-cache");
  expectSecurityHeaders(response);
});

for (const path of [
  "/assets/missing.js",
  "/missing.png",
  "/projects/report.pdf",
]) {
  test(`answers 404 for the missing file ${path}`, async ({ request }) => {
    const response = await request.get(path);
    expect(response.status()).toBe(404);
    expect(await response.text()).not.toContain('<div id="root">');
    expect(response.headers()["cache-control"] ?? "").not.toContain(
      "immutable",
    );
    expectSecurityHeaders(response);
  });
}

test("serves nothing from outside the web root", async ({ request }) => {
  const response = await request.get("/..%2f..%2f..%2fetc%2fpasswd");
  expect([400, 404]).toContain(response.status());
  expect(await response.text()).not.toContain("root:");
});

test("proxies the API under /api/ with the prefix stripped", async ({
  request,
}) => {
  const response = await request.get("/api/health");
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ status: "ok" });
  expectSecurityHeaders(response);
});

test("names no nginx version", async ({ request }) => {
  const response = await request.get("/");
  expect(response.headers().server).toBe("nginx");
});

test("redirects /api to /api/ without naming a host or port", async ({
  request,
}) => {
  const response = await request.get("/api", { maxRedirects: 0 });
  expect(response.status()).toBe(301);
  expect(response.headers().location).toBe("/api/");
});

test("compresses the bundles", async ({ request }) => {
  const html = await (await request.get("/")).text();
  const script = /src="(\/assets\/[^"]+\.js)"/.exec(html)?.[1];
  if (!script) throw new Error("index.html names no bundle under /assets/");
  const response = await request.get(script, {
    headers: { "Accept-Encoding": "gzip" },
  });
  expect(response.headers()["content-encoding"]).toBe("gzip");
});
