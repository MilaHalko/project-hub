import { useEffect, useRef, type RefObject } from "react";
import { NavigationType, useLocation, useNavigationType } from "react-router";

export function useFocusHeadingOnNavigate(
  container: RefObject<HTMLElement | null>,
): void {
  const { pathname } = useLocation();
  const navigationType = useNavigationType();
  const previous = useRef(pathname);
  const startedWithoutHeading = useRef(false);
  const firstChange = useRef(true);

  useEffect(() => {
    startedWithoutHeading.current = !container.current?.querySelector("h1");
  }, [container]);

  useEffect(() => {
    if (previous.current === pathname) return;
    previous.current = pathname;
    const redirectedOnLoad =
      firstChange.current &&
      navigationType === NavigationType.Replace &&
      startedWithoutHeading.current;
    firstChange.current = false;
    if (redirectedOnLoad) return;
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
  }, [pathname, navigationType, container]);
}
