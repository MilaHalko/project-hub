import type { ReactNode } from "react";
import styles from "./Banner.module.css";

export function Banner({
  tag,
  title,
  aside,
  actions,
  children,
}: {
  tag: ReactNode;
  title: string;
  aside?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={styles.banner}>
      {aside}
      <div className={styles.text}>
        <p className={styles.tag}>{tag}</p>
        <h1 tabIndex={-1} className={styles.title}>
          {title}
        </h1>
        <div className={styles.body}>{children}</div>
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  );
}
