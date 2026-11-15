import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type Ref,
} from "react";
import styles from "./Field.module.css";

export type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
  ref?: Ref<HTMLInputElement>;
};

export function Field({
  label,
  hint,
  error,
  id,
  trailing,
  ...input
}: FieldProps & { trailing?: ReactNode }) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const describedBy =
    [hint ? hintId : "", error ? errorId : ""].filter(Boolean).join(" ") ||
    undefined;
  return (
    <div className={styles.field}>
      <label htmlFor={inputId} className={styles.label}>
        {label}
      </label>
      <div className={styles.box} data-invalid={Boolean(error)}>
        <input
          {...input}
          id={inputId}
          className={styles.input}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
        {trailing}
      </div>
      {hint && (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  );
}
