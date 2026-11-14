import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import styles from "./LoaderBar.module.css";

export function LoaderBar() {
  const running = useIsFetching() + useIsMutating();
  if (running === 0) return null;
  return (
    <div role="progressbar" aria-label="Loading" className={styles.bar}>
      <div className={styles.runner} />
    </div>
  );
}
