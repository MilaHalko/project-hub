import { LayoutGrid, Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import styles from "./Layout.module.css";

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();
  const [menuPath, setMenuPath] = useState(pathname);
  const menuButton = useRef<HTMLButtonElement>(null);

  if (pathname !== menuPath) {
    setMenuPath(pathname);
    setMenuOpen(false);
  }

  useEffect(() => {
    if (!menuOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setMenuOpen(false);
      menuButton.current?.focus();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [menuOpen]);

  return (
    <div className={styles.shell}>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true" />
          Project Hub
        </div>
        <button
          ref={menuButton}
          type="button"
          className={styles.menuButton}
          aria-expanded={menuOpen}
          aria-controls="main-nav"
          onClick={() => {
            setMenuOpen((open) => !open);
          }}
        >
          {menuOpen ? (
            <X size={16} aria-hidden="true" />
          ) : (
            <Menu size={16} aria-hidden="true" />
          )}
          Menu
        </button>
        <nav
          id="main-nav"
          aria-label="Main"
          className={styles.nav}
          data-open={menuOpen}
        >
          <NavLink
            to="/"
            end
            className={styles.link}
            onClick={() => {
              setMenuOpen(false);
            }}
          >
            <LayoutGrid size={16} aria-hidden="true" />
            Projects
          </NavLink>
        </nav>
      </header>
      <main id="main" tabIndex={-1} className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
