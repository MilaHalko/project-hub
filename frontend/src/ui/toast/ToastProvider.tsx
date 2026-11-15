import { CircleAlert, CircleCheck, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ToastContext, type ToastApi } from "./toastContext";
import styles from "./Toasts.module.css";

const SUCCESS_MS = 5000;

type Kind = "success" | "error";

interface Toast {
  id: number;
  kind: Kind;
  text: string;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);
  const timers = useRef(new Map<number, number>());
  const holds = useRef(new Map<number, { pointer: boolean; focus: boolean }>());
  const wrapper = useRef<HTMLDivElement>(null);
  const lastOutside = useRef<Element | null>(null);

  useEffect(() => {
    function remember(event: FocusEvent) {
      const target = event.target;
      if (target instanceof Element && !wrapper.current?.contains(target)) {
        lastOutside.current = target;
      }
    }
    document.addEventListener("focusin", remember);
    return () => {
      document.removeEventListener("focusin", remember);
    };
  }, []);

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
    holds.current.delete(id);
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const startTimer = useCallback(
    (id: number) => {
      window.clearTimeout(timers.current.get(id));
      timers.current.set(
        id,
        window.setTimeout(() => {
          dismiss(id);
        }, SUCCESS_MS),
      );
    },
    [dismiss],
  );

  const hold = useCallback(
    (id: number, part: "pointer" | "focus", on: boolean) => {
      if (!timers.current.has(id)) return;
      const state = holds.current.get(id) ?? { pointer: false, focus: false };
      state[part] = on;
      holds.current.set(id, state);
      if (state.pointer || state.focus) {
        window.clearTimeout(timers.current.get(id));
      } else {
        startTimer(id);
      }
    },
    [startTimer],
  );

  const dismissWithFocus = useCallback(
    (id: number, button: HTMLButtonElement) => {
      if (document.activeElement === button) {
        const buttons = Array.from(
          wrapper.current?.querySelectorAll<HTMLButtonElement>("button") ?? [],
        );
        const next = buttons[buttons.indexOf(button) + 1];
        if (next !== undefined) {
          next.focus();
        } else {
          const back = lastOutside.current;
          const target =
            back instanceof HTMLElement && back.isConnected
              ? back
              : document.getElementById("main");
          target?.focus();
        }
      }
      dismiss(id);
    },
    [dismiss],
  );

  const add = useCallback(
    (kind: Kind, text: string) => {
      const id = nextId.current++;
      setToasts((current) => [...current, { id, kind, text }]);
      if (kind === "success") {
        startTimer(id);
      }
    },
    [startTimer],
  );

  useEffect(() => {
    const active = timers.current;
    return () => {
      active.forEach((timer) => {
        window.clearTimeout(timer);
      });
      active.clear();
    };
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (text) => {
        add("success", text);
      },
      error: (text) => {
        add("error", text);
      },
    }),
    [add],
  );

  const render = (kind: Kind) =>
    toasts
      .filter((toast) => toast.kind === kind)
      .map((toast) => (
        <div
          key={toast.id}
          className={styles.toast}
          onMouseEnter={() => {
            hold(toast.id, "pointer", true);
          }}
          onMouseLeave={() => {
            hold(toast.id, "pointer", false);
          }}
          onFocus={() => {
            hold(toast.id, "focus", true);
          }}
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) {
              hold(toast.id, "focus", false);
            }
          }}
        >
          {kind === "success" ? (
            <CircleCheck className={styles.success} size={18} aria-hidden />
          ) : (
            <CircleAlert className={styles.error} size={18} aria-hidden />
          )}
          <p className={styles.text}>{toast.text}</p>
          <button
            type="button"
            className={styles.dismiss}
            aria-label="Dismiss notification"
            onClick={(event) => {
              dismissWithFocus(toast.id, event.currentTarget);
            }}
          >
            <X size={16} aria-hidden />
          </button>
        </div>
      ));

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div ref={wrapper} className={styles.wrapper}>
        <div
          role="status"
          aria-atomic="false"
          aria-relevant="additions"
          className={styles.region}
        >
          {render("success")}
        </div>
        <div
          role="alert"
          aria-atomic="false"
          aria-relevant="additions"
          className={styles.region}
        >
          {render("error")}
        </div>
      </div>
    </ToastContext.Provider>
  );
}
