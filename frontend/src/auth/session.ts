import { postLogin, postRegister } from "../api/auth";
import { setToken } from "./tokenStore";

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
