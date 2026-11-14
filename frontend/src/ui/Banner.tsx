import type { ReactNode } from "react";
import styles from "./Banner.module.css";

export function Banner({
  tag,
  title,
  children,
}: {
  tag: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className={styles.banner}>
      <p className={styles.tag}>{tag}</p>
      <h1 className={styles.title}>{title}</h1>
      <div className={styles.body}>{children}</div>
    </div>
  );
}
