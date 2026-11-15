import { postLogin, postLogout, postRegister, putPassword } from "../api/auth";
import { clearToken, setToken } from "./tokenStore";

export class LoginAfterRegisterError extends Error {
  constructor(options: { cause: unknown }) {
    super("Account created, but logging in failed", options);
    this.name = "LoginAfterRegisterError";
  }
}

export async function logIn(login: string, password: string): Promise<void> {
  const { access_token } = await postLogin({ login, password });
  setToken(access_token);
}

export async function register(
  login: string,
  password: string,
  repeatPassword: string,
): Promise<void> {
  await postRegister({
    login,
    password,
    repeat_password: repeatPassword,
  });
  try {
    await logIn(login, password);
  } catch (error) {
    throw new LoginAfterRegisterError({ cause: error });
  }
}

export async function logOut(): Promise<void> {
  try {
    await postLogout();
  } catch {
    return;
  } finally {
    clearToken("logout");
  }
}

export async function changePassword(
  current: string,
  next: string,
  repeat: string,
): Promise<void> {
  const { access_token } = await putPassword({
    current_password: current,
    new_password: next,
    repeat_new_password: repeat,
  });
  setToken(access_token);
}
