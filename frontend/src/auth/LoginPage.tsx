import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type SubmitEvent } from "react";
import { Link, Navigate, useLocation, useSearchParams } from "react-router";
import { ApiError, fieldErrors, messageFor } from "../api/errors";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";
import { PasswordField } from "../ui/PasswordField";
import styles from "./LoginPage.module.css";
import { safeNext } from "./safeNext";
import { logIn } from "./session";
import { useToken } from "./tokenStore";

const reasonTexts = new Map([
  ["expired", "Your session expired. Log in again."],
  ["logout", "You are logged out."],
  ["created", "Account created. Log in."],
]);

function reasonText(state: unknown): string | null {
  if (typeof state !== "object" || state === null || !("reason" in state)) {
    return null;
  }
  return typeof state.reason === "string"
    ? (reasonTexts.get(state.reason) ?? null)
    : null;
}

type Errors = { login?: string; password?: string };

function serverErrors(error: Error | null): {
  fields: Errors;
  form: string | null;
} {
  if (error === null) return { fields: {}, form: null };
  if (error instanceof ApiError && error.status === 401) {
    return { fields: {}, form: "Wrong login or password. Try again." };
  }
  if (error instanceof ApiError && error.status === 422) {
    const { fields, form } = fieldErrors(error);
    return { fields: { login: fields.login, password: fields.password }, form };
  }
  return { fields: {}, form: messageFor(error) };
}

export function LoginPage() {
  const token = useToken();
  const location = useLocation();
  const [params] = useSearchParams();
  const next = params.get("next");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [clientErrors, setClientErrors] = useState<Errors>({});
  const loginInput = useRef<HTMLInputElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);
  const mutation = useMutation({
    mutationFn: () => logIn(login, password),
  });

  if (token) return <Navigate to={safeNext(next)} replace />;

  const server = serverErrors(mutation.error);
  const errors: Errors = {
    login: clientErrors.login ?? server.fields.login,
    password: clientErrors.password ?? server.fields.password,
  };
  const status = reasonText(location.state);

  function focusFirstInvalid(found: Errors) {
    if (found.login) loginInput.current?.focus();
    else if (found.password) passwordInput.current?.focus();
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    const found: Errors = {
      login: login.trim() === "" ? "Enter your login" : undefined,
      password: password === "" ? "Enter your password" : undefined,
    };
    setClientErrors(found);
    mutation.reset();
    if (found.login || found.password) {
      focusFirstInvalid(found);
      return;
    }
    mutation.mutate(undefined, {
      onError: (error) => {
        focusFirstInvalid(serverErrors(error).fields);
      },
    });
  }

  return (
    <>
      <h1 className={styles.title}>Log in</h1>
      <p className={styles.sub}>
        No account?{" "}
        <Link
          to={
            next === null
              ? "/register"
              : `/register?next=${encodeURIComponent(next)}`
          }
        >
          Create one
        </Link>
      </p>
      {server.form !== null ? (
        <p role="alert" className={styles.notice}>
          {server.form}
        </p>
      ) : (
        status !== null && (
          <p role="status" className={styles.notice}>
            {status}
          </p>
        )
      )}
      <form noValidate onSubmit={submit}>
        <Field
          ref={loginInput}
          label="Login"
          name="login"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          value={login}
          error={errors.login}
          onChange={(event) => {
            setLogin(event.target.value);
          }}
        />
        <PasswordField
          ref={passwordInput}
          label="Password"
          name="password"
          autoComplete="current-password"
          value={password}
          error={errors.password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
        />
        <Button type="submit" wide busy={mutation.isPending}>
          Log in
        </Button>
      </form>
    </>
  );
}
