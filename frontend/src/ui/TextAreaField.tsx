import { useId, type Ref, type TextareaHTMLAttributes } from "react";
import styles from "./Field.module.css";

export function TextAreaField({
  label,
  hint,
  error,
  id,
  ref,
  ...textarea
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  hint?: string;
  error?: string;
  ref?: Ref<HTMLTextAreaElement>;
}) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const describedBy =
    [error ? errorId : "", hint ? hintId : ""].filter(Boolean).join(" ") ||
    undefined;
  return (
    <div className={styles.field}>
      <label htmlFor={inputId} className={styles.label}>
        {label}
      </label>
      <div className={styles.box} data-invalid={Boolean(error)}>
        <textarea
          {...textarea}
          ref={ref}
          id={inputId}
          className={[styles.input, styles.textarea].join(" ")}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
      </div>
      {error && (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      )}
      {hint && (
        <p id={hintId} className={[styles.hint, styles.counter].join(" ")}>
          {hint}
        </p>
      )}
    </div>
  );
}
