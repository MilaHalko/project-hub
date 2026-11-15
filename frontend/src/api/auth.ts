import { apiFetch } from "./client";

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type User = { id: string; login: string; created_at: string };

export function postLogin(body: {
  login: string;
  password: string;
}): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/login", { method: "POST", body });
}

export function getMe(): Promise<User> {
  return apiFetch<User>("/users/me");
}

export function postRegister(body: {
  login: string;
  password: string;
  repeat_password: string;
}): Promise<User> {
  return apiFetch<User>("/auth", { method: "POST", body });
}
