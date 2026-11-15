import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type SubmitEvent } from "react";
import { ApiError, fieldErrors, messageFor } from "../api/errors";
import { checkNewPassword } from "../auth/passwordRules";
import { changePassword } from "../auth/session";
import { Button } from "../ui/Button";
import { PasswordField } from "../ui/PasswordField";
import { useToast } from "../ui/toast/useToast";
import styles from "./ChangePasswordForm.module.css";

type Errors = { current?: string; next?: string; repeat?: string };

function serverErrors(error: Error | null): {
  fields: Errors;
  form: string | null;
} {
  if (error === null) return { fields: {}, form: null };
  if (error instanceof ApiError && error.status === 400) {
    return {
      fields: { current: "Current password is wrong. Try again." },
      form: null,
    };
  }
  if (error instanceof ApiError && error.status === 422) {
    const { fields, form } = fieldErrors(error);
    return {
      fields: {
        current: fields.current_password,
        next: fields.new_password,
        repeat: fields.repeat_new_password,
      },
      form,
    };
  }
  return { fields: {}, form: messageFor(error) };
}

export function ChangePasswordForm({ login }: { login: string }) {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [clientErrors, setClientErrors] = useState<Errors>({});
  const currentInput = useRef<HTMLInputElement>(null);
  const nextInput = useRef<HTMLInputElement>(null);
  const repeatInput = useRef<HTMLInputElement>(null);
  const mutation = useMutation({
    mutationFn: async () => {
      await changePassword(current, next, repeat);
    },
    onSuccess: () => {
      toast.success("Password changed");
    },
  });

  const server = serverErrors(mutation.error);
  const errors: Errors = {
    current: clientErrors.current ?? server.fields.current,
    next: clientErrors.next ?? server.fields.next,
    repeat: clientErrors.repeat ?? server.fields.repeat,
  };

  function focusFirstInvalid(found: Errors) {
    if (found.current) currentInput.current?.focus();
    else if (found.next) nextInput.current?.focus();
    else if (found.repeat) repeatInput.current?.focus();
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    const found: Errors = {
      current: current === "" ? "Enter your current password" : undefined,
      next:
        checkNewPassword(next, login) ??
        (next === current
          ? "New password must differ from the current one"
          : undefined),
      repeat: repeat === next ? undefined : "Passwords do not match",
    };
    setClientErrors(found);
    mutation.reset();
    if (found.current || found.next || found.repeat) {
      focusFirstInvalid(found);
      return;
    }
    mutation.mutate(undefined, {
      onSuccess: () => {
        setCurrent("");
        setNext("");
        setRepeat("");
      },
      onError: (error) => {
        focusFirstInvalid(serverErrors(error).fields);
      },
    });
  }

  return (
    <section className={styles.panel}>
      <h2 className={styles.title}>Change password</h2>
      <p className={styles.sub}>
        Changing the password logs you out on other devices.
      </p>
      {server.form !== null && (
        <p role="alert" className={styles.notice}>
          {server.form}
        </p>
      )}
      <form noValidate onSubmit={submit}>
        <PasswordField
          ref={currentInput}
          label="Current password"
          name="current_password"
          autoComplete="current-password"
          value={current}
          error={errors.current}
          onChange={(event) => {
            setCurrent(event.target.value);
          }}
        />
        <PasswordField
          ref={nextInput}
          label="New password"
          name="new_password"
          hint="8–128 characters"
          autoComplete="new-password"
          value={next}
          error={errors.next}
          onChange={(event) => {
            setNext(event.target.value);
          }}
        />
        <PasswordField
          ref={repeatInput}
          label="Repeat new password"
          name="repeat_new_password"
          autoComplete="new-password"
          value={repeat}
          error={errors.repeat}
          onChange={(event) => {
            setRepeat(event.target.value);
          }}
        />
        <Button type="submit" busy={mutation.isPending}>
          Change password
        </Button>
      </form>
    </section>
  );
}
