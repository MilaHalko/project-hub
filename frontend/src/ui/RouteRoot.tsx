import { useRef } from "react";
import { Outlet } from "react-router";
import styles from "./RouteRoot.module.css";
import { useFocusHeadingOnNavigate } from "./useFocusHeadingOnNavigate";

export function RouteRoot() {
  const container = useRef<HTMLDivElement>(null);
  useFocusHeadingOnNavigate(container);
  return (
    <div ref={container} className={styles.root}>
      <Outlet />
    </div>
  );
}
