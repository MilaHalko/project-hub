import { postLogin } from "../api/auth";
import { setToken } from "./tokenStore";

export async function logIn(login: string, password: string): Promise<void> {
  const { access_token } = await postLogin({ login, password });
  setToken(access_token);
}
