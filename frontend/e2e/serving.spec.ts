import { expect, test, type APIResponse } from "@playwright/test";

const contentSecurityPolicy =
  "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'";

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

const MB = 1_048_576;

function multipartOf(bytes: number) {
  return {
    files: {
      name: "big.bin",
      mimeType: "application/octet-stream",
      buffer: Buffer.alloc(bytes),
    },
  };
}

test("answers an upload above the request limit with a JSON 413", async ({
  request,
}) => {
  const response = await request.post("/api/project/1/documents", {
    multipart: multipartOf(60 * MB),
  });
  expect(response.status()).toBe(413);
  expect(response.headers()["content-type"]).toContain("application/json");
  expect(await response.json()).toEqual({
    detail: "The request is larger than the server accepts",
  });
  expectSecurityHeaders(response);
});

test("passes a multi-file upload above 11 MB on to the API", async ({
  request,
}) => {
  const response = await request.post("/api/project/1/documents", {
    multipart: {
      first: multipartOf(5 * MB).files,
      second: multipartOf(5 * MB).files,
      third: multipartOf(5 * MB).files,
    },
  });
  expect(response.status()).toBe(401);
  expect(response.headers()["content-type"]).toContain("application/json");
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

test("serves the API schema at /openapi.json", async ({ request }) => {
  const response = await request.get("/openapi.json");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("application/json");
  const schema = (await response.json()) as {
    paths: Record<string, unknown>;
    servers: { url: string }[];
  };
  expect(schema.servers).toEqual([{ url: "/api" }]);
  expect(Object.keys(schema.paths)).toContain("/health");
});

test("serves Swagger at /docs with a policy that lets it load", async ({
  request,
}) => {
  const response = await request.get("/docs");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("text/html");
  expect(await response.text()).toContain("swagger-ui");
  const policy = response.headers()["content-security-policy"];
  expect(policy).toContain(
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
  );
  expect(policy).toContain("frame-ancestors 'none'");
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
});
