import { useSyncExternalStore } from "react";

export type EndReason = "expired" | "logout";

const KEY = "project-hub.token";
const listeners = new Set<() => void>();
let endReason: EndReason | null = null;

function notify() {
  listeners.forEach((listener) => {
    listener();
  });
}

export function getToken(): string | null {
  return sessionStorage.getItem(KEY) || null;
}

export function setToken(token: string): void {
  sessionStorage.setItem(KEY, token);
  endReason = null;
  notify();
}

export function clearToken(reason: EndReason): void {
  sessionStorage.removeItem(KEY);
  endReason = reason;
  notify();
}

export function getEndReason(): EndReason | null {
  return endReason;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useToken(): string | null {
  return useSyncExternalStore(subscribe, getToken);
}
