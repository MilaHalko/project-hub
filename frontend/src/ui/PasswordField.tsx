import { useState } from "react";
import { Field, type FieldProps } from "./Field";
import styles from "./Field.module.css";

export function PasswordField(props: Omit<FieldProps, "type">) {
  const [shown, setShown] = useState(false);
  return (
    <Field
      {...props}
      type={shown ? "text" : "password"}
      trailing={
        <button
          type="button"
          className={styles.toggle}
          aria-label="Show password"
          aria-pressed={shown}
          onClick={() => {
            setShown((value) => !value);
          }}
        >
          Show
        </button>
      }
    />
  );
}
