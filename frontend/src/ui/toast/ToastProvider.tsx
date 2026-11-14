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

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const add = useCallback(
    (kind: Kind, text: string) => {
      const id = nextId.current++;
      setToasts((current) => [...current, { id, kind, text }]);
      if (kind === "success") {
        timers.current.set(
          id,
          window.setTimeout(() => {
            dismiss(id);
          }, SUCCESS_MS),
        );
      }
    },
    [dismiss],
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
        <div key={toast.id} className={styles.toast}>
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
            onClick={() => {
              dismiss(toast.id);
            }}
          >
            <X size={16} aria-hidden />
          </button>
        </div>
      ));

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className={styles.wrapper}>
        <div role="status" className={styles.region}>
          {render("success")}
        </div>
        <div role="alert" className={styles.region}>
          {render("error")}
        </div>
      </div>
    </ToastContext.Provider>
  );
}
