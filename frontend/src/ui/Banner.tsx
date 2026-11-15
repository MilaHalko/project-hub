import type { ReactNode } from "react";
import styles from "./Banner.module.css";

export function Banner({
  tag,
  title,
  aside,
  children,
}: {
  tag: string;
  title: string;
  aside?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={styles.banner}>
      {aside}
      <div className={styles.text}>
        <p className={styles.tag}>{tag}</p>
        <h1 className={styles.title}>{title}</h1>
        <div className={styles.body}>{children}</div>
      </div>
    </div>
  );
}
