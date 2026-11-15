const LOGIN = /^[A-Za-z0-9_.-]{3,32}$/;
const PRINTABLE_ASCII = /^[\x20-\x7E]*$/;

export function checkLogin(login: string): string | null {
  return LOGIN.test(login)
    ? null
    : "Use 3–32 characters: letters, digits, _ . -";
}

export function checkNewPassword(
  password: string,
  login: string,
): string | null {
  if (password.length < 8 || password.length > 128) {
    return "Use 8–128 characters";
  }
  if (!PRINTABLE_ASCII.test(password)) {
    return "Use only English letters, digits, keyboard symbols and spaces";
  }
  if (password === login) return "Password must not equal the login";
  return null;
}
