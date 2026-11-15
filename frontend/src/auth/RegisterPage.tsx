import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type SubmitEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { ApiError, fieldErrors, messageFor } from "../api/errors";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";
import { PasswordField } from "../ui/PasswordField";
import { useToast } from "../ui/toast/useToast";
import styles from "./AuthForm.module.css";
import { checkLogin, checkNewPassword } from "./passwordRules";
import { safeNext } from "./safeNext";
import { LoginAfterRegisterError, register } from "./session";
import { useToken } from "./tokenStore";

type Errors = { login?: string; password?: string; repeat?: string };

function serverErrors(error: Error | null): {
  fields: Errors;
  form: string | null;
} {
  if (error === null || error instanceof LoginAfterRegisterError) {
    return { fields: {}, form: null };
  }
  if (error instanceof ApiError && error.status === 409) {
    return {
      fields: { login: "That login is taken. Try another." },
      form: null,
    };
  }
  if (error instanceof ApiError && error.status === 422) {
    const { fields, form } = fieldErrors(error);
    return {
      fields: {
        login: fields.login,
        password: fields.password,
        repeat: fields.repeat_password,
      },
      form,
    };
  }
  return { fields: {}, form: messageFor(error) };
}

export function RegisterPage() {
  const token = useToken();
  const navigate = useNavigate();
  const toast = useToast();
  const [params] = useSearchParams();
  const next = params.get("next");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [clientErrors, setClientErrors] = useState<Errors>({});
  const loginInput = useRef<HTMLInputElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);
  const repeatInput = useRef<HTMLInputElement>(null);
  const mutation = useMutation({
    mutationFn: async () => {
      await register(login, password, repeat);
    },
    onSuccess: () => {
      toast.success("Account created");
    },
  });

  if (token) return <Navigate to={safeNext(next)} replace />;

  const server = serverErrors(mutation.error);
  const errors: Errors = {
    login: clientErrors.login ?? server.fields.login,
    password: clientErrors.password ?? server.fields.password,
    repeat: clientErrors.repeat ?? server.fields.repeat,
  };

  function focusFirstInvalid(found: Errors) {
    if (found.login) loginInput.current?.focus();
    else if (found.password) passwordInput.current?.focus();
    else if (found.repeat) repeatInput.current?.focus();
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    const found: Errors = {
      login: checkLogin(login) ?? undefined,
      password: checkNewPassword(password, login) ?? undefined,
      repeat: repeat === password ? undefined : "Passwords do not match",
    };
    setClientErrors(found);
    mutation.reset();
    if (found.login || found.password || found.repeat) {
      focusFirstInvalid(found);
      return;
    }
    mutation.mutate(undefined, {
      onError: (error) => {
        if (error instanceof LoginAfterRegisterError) {
          void navigate(
            next === null
              ? "/login"
              : `/login?next=${encodeURIComponent(next)}`,
            { replace: true, state: { reason: "created", login } },
          );
          return;
        }
        focusFirstInvalid(serverErrors(error).fields);
      },
    });
  }

  const loginQuery = next === null ? "" : `?next=${encodeURIComponent(next)}`;

  return (
    <>
      <h1 tabIndex={-1} className={styles.title}>
        Create account
      </h1>
      <p className={styles.sub}>
        Have an account? <Link to={`/login${loginQuery}`}>Log in</Link>
      </p>
      {server.form !== null && (
        <p role="alert" className={styles.notice}>
          {server.form}
        </p>
      )}
      <form noValidate onSubmit={submit}>
        <Field
          ref={loginInput}
          label="Login"
          name="login"
          hint="3–32 characters: letters, digits, _ . -"
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
          hint="8–128 characters"
          autoComplete="new-password"
          value={password}
          error={errors.password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
        />
        <PasswordField
          ref={repeatInput}
          label="Repeat password"
          name="repeat_password"
          autoComplete="new-password"
          value={repeat}
          error={errors.repeat}
          onChange={(event) => {
            setRepeat(event.target.value);
          }}
        />
        <Button type="submit" wide busy={mutation.isPending}>
          Create account
        </Button>
      </form>
    </>
  );
}
