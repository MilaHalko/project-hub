import { Outlet } from "react-router";
import styles from "./AuthLayout.module.css";

export function AuthLayout() {
  return (
    <div className={styles.auth}>
      <header className={styles.art}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true" />
          Project Hub
        </div>
        <div>
          <p className={styles.tag}>PROJECT_HUB</p>
          <p className={styles.headline}>
            Your team&apos;s projects and documents
          </p>
          <p className={styles.lead}>
            Create projects, upload files, invite people.
          </p>
        </div>
      </header>
      <main id="main" className={styles.main}>
        <div className={styles.content}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
