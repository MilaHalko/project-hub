import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, Ref } from "react";
import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "danger";

export function buttonClassName({
  variant = "primary",
  wide = false,
}: { variant?: Variant; wide?: boolean } = {}): string {
  return [styles.button, styles[variant], wide ? styles.wide : ""]
    .filter(Boolean)
    .join(" ");
}

export function Button({
  variant,
  busy = false,
  wide,
  className,
  type = "button",
  onClick,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  busy?: boolean;
  wide?: boolean;
  ref?: Ref<HTMLButtonElement>;
}) {
  return (
    <button
      {...rest}
      type={type}
      className={[buttonClassName({ variant, wide }), className]
        .filter(Boolean)
        .join(" ")}
      aria-busy={busy || undefined}
      onClick={(event) => {
        if (busy) {
          event.preventDefault();
          return;
        }
        onClick?.(event);
      }}
    >
      {busy && (
        <LoaderCircle className={styles.spinner} size={16} aria-hidden />
      )}
      {children}
    </button>
  );
}
