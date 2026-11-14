import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { setToken } from "../auth/tokenStore";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  setToken("");
  sessionStorage.clear();
});
