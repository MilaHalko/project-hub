import { useEffect, useRef, type RefObject } from "react";
import { useLocation } from "react-router";

export function useFocusHeadingOnNavigate(
  container: RefObject<HTMLElement | null>,
): void {
  const { pathname } = useLocation();
  const previous = useRef(pathname);

  useEffect(() => {
    if (previous.current === pathname) return;
    previous.current = pathname;
    const root = container.current;
    if (!root) return;

    function focusHeading(): boolean {
      const heading = root?.querySelector("h1");
      if (!heading) return false;
      if (!heading.hasAttribute("tabindex")) heading.tabIndex = -1;
      heading.focus();
      return true;
    }

    if (focusHeading()) return;

    const observer = new MutationObserver(() => {
      if (focusHeading()) stop();
    });
    function stop() {
      observer.disconnect();
      document.removeEventListener("pointerdown", stop, true);
      document.removeEventListener("keydown", stop, true);
    }
    observer.observe(root, { childList: true, subtree: true });
    document.addEventListener("pointerdown", stop, true);
    document.addEventListener("keydown", stop, true);
    return stop;
  }, [pathname, container]);
}
