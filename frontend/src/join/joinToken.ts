const KEY = "project-hub.join-token";

export function saveJoinToken(token: string): void {
  sessionStorage.setItem(KEY, token);
}

export function readJoinToken(): string | null {
  return sessionStorage.getItem(KEY);
}

export function clearJoinToken(): void {
  sessionStorage.removeItem(KEY);
}
