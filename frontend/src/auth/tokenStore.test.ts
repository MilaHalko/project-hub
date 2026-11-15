import { expect, test, vi } from "vitest";
import {
  clearToken,
  getEndReason,
  getToken,
  setToken,
  subscribe,
} from "./tokenStore";

test("keeps the token in sessionStorage only", () => {
  setToken("a");

  expect(getToken()).toBe("a");
  expect(sessionStorage.getItem("project-hub.token")).toBe("a");
  expect(localStorage.length).toBe(0);
});

test("clearing the token keeps the reason and tells subscribers", () => {
  setToken("a");
  const listener = vi.fn();
  const unsubscribe = subscribe(listener);

  clearToken("expired");

  expect(getToken()).toBeNull();
  expect(sessionStorage.getItem("project-hub.token")).toBeNull();
  expect(getEndReason()).toBe("expired");
  expect(listener).toHaveBeenCalled();
  unsubscribe();
});

test("a new token forgets the end reason", () => {
  clearToken("logout");

  setToken("b");

  expect(getEndReason()).toBeNull();
});
