import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import styles from "./Dialog.module.css";

export function Dialog({
  open,
  title,
  onClose,
  role = "dialog",
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  role?: "dialog" | "alertdialog";
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [nativeCloses, setNativeCloses] = useState(0);
  const focusedBeforeCancel = useRef<Element | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const focused = focusedBeforeCancel.current;
    focusedBeforeCancel.current = null;
    if (open && !dialog.open) {
      dialog.showModal();
      if (focused instanceof HTMLElement && dialog.contains(focused)) {
        focused.focus();
      }
    }
    if (!open && dialog.open) dialog.close();
  }, [open, nativeCloses]);

  return (
    <dialog
      ref={ref}
      role={role}
      aria-labelledby={titleId}
      className={styles.dialog}
      onClose={() => {
        onClose();
        // Chromium closes the dialog itself after repeated Esc (non-cancelable
        // cancel); when the parent keeps it open, the effect reopens it and
        // puts the focus back where it was before the cancel.
        setNativeCloses((count) => count + 1);
      }}
      onCancel={(event) => {
        focusedBeforeCancel.current = document.activeElement;
        event.preventDefault();
        onClose();
      }}
    >
      <h2 id={titleId} className={styles.title}>
        {title}
      </h2>
      {children}
    </dialog>
  );
}
