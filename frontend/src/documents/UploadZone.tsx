import { LoaderCircle } from "lucide-react";
import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { Button } from "../ui/Button";
import { FileTile } from "./FileTile";
import { formatSize } from "./fileRules";
import styles from "./UploadZone.module.css";
import { useUploadQueue, type UploadItem } from "./useUploadQueue";

function carriesFiles(event: { dataTransfer: DataTransfer | null }): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

function useKeepDropsInApp(zone: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    function keep(event: globalThis.DragEvent) {
      if (!carriesFiles(event)) return;
      event.preventDefault();
      const inside =
        event.target instanceof Node && zone.current?.contains(event.target);
      if (!inside && event.dataTransfer) event.dataTransfer.dropEffect = "none";
    }
    window.addEventListener("dragover", keep);
    window.addEventListener("drop", keep);
    return () => {
      window.removeEventListener("dragover", keep);
      window.removeEventListener("drop", keep);
    };
  }, [zone]);
}

function UploadRow({
  item,
  onDismiss,
}: {
  item: UploadItem;
  onDismiss: () => void;
}) {
  return (
    <li className={styles.item}>
      <FileTile name={item.file.name} />
      <span className={styles.itemName}>
        <span className={styles.fileName}>{item.file.name}</span>
        {item.state === "failed" ? (
          <span className={styles.error}>{item.error}</span>
        ) : (
          <span className={styles.meta}>{formatSize(item.file.size)}</span>
        )}
      </span>
      {item.state === "failed" ? (
        <Button
          variant="secondary"
          className={styles.dismiss}
          aria-label={`Dismiss ${item.file.name}`}
          onClick={onDismiss}
        >
          Dismiss
        </Button>
      ) : (
        <span className={styles.state}>
          {item.state === "uploading" && (
            <LoaderCircle className={styles.spinner} size={14} aria-hidden />
          )}
          {item.state === "uploading" ? "Uploading…" : "Waiting"}
        </span>
      )}
    </li>
  );
}

export function UploadZone({ projectId }: { projectId: string }) {
  const { items, announcement, add, dismiss } = useUploadQueue(projectId);
  const zone = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const uploads = useRef<HTMLUListElement>(null);
  const focusAfterDismiss = useRef<number | null>(null);

  useEffect(() => {
    const dismissedAt = focusAfterDismiss.current;
    if (dismissedAt === null) return;
    focusAfterDismiss.current = null;
    const dismissButtons =
      uploads.current?.querySelectorAll<HTMLElement>("button") ?? [];
    const next =
      dismissButtons[Math.min(dismissedAt, dismissButtons.length - 1)];
    (next ?? input.current)?.focus();
  }, [items]);
  const inputId = useId();
  const [dragDepth, setDragDepth] = useState(0);
  useKeepDropsInApp(zone);

  function enter(event: DragEvent) {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    setDragDepth((depth) => depth + 1);
  }

  function leave(event: DragEvent) {
    if (!carriesFiles(event)) return;
    setDragDepth((depth) => Math.max(0, depth - 1));
  }

  function over(event: DragEvent) {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragDepth(0);
    add(Array.from(event.dataTransfer.files));
  }

  return (
    <>
      <div
        ref={zone}
        className={[styles.zone, dragDepth > 0 ? styles.over : ""]
          .filter(Boolean)
          .join(" ")}
        onDragEnter={enter}
        onDragLeave={leave}
        onDragOver={over}
        onDrop={drop}
      >
        <input
          ref={input}
          id={inputId}
          className={styles.input}
          type="file"
          multiple
          accept=".pdf,.docx"
          onChange={(event) => {
            add(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        {dragDepth > 0 && <p className={styles.drop}>Drop to upload</p>}
        <div className={dragDepth > 0 ? styles.visuallyHidden : undefined}>
          <p>
            <span className={styles.dragText}>
              Drop PDF or DOCX files here or{" "}
            </span>
            <label htmlFor={inputId} className={styles.choose}>
              Choose files
            </label>
          </p>
          <p className={styles.hint}>PDF or DOCX, up to 10 MB each</p>
        </div>
      </div>
      {items.length > 0 && (
        <ul ref={uploads} className={styles.items} aria-label="Uploads">
          {items.map((item) => (
            <UploadRow
              key={item.key}
              item={item}
              onDismiss={() => {
                focusAfterDismiss.current = items
                  .filter(({ state }) => state === "failed")
                  .findIndex(({ key }) => key === item.key);
                dismiss(item.key);
              }}
            />
          ))}
        </ul>
      )}
      <div
        role="status"
        aria-label="Upload messages"
        className={styles.visuallyHidden}
      >
        {announcement}
      </div>
    </>
  );
}
