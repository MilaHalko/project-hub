const BASE = "http://app.invalid";
const AUTH_PAGES = /^\/(login|register)\/?$/i;

export function safeNext(next: string | null): string {
  if (!next?.startsWith("/")) return "/";
  let url: URL;
  try {
    url = new URL(next, BASE);
  } catch {
    return "/";
  }
  if (url.origin !== BASE || AUTH_PAGES.test(url.pathname)) return "/";
  return url.pathname + url.search + url.hash;
}
