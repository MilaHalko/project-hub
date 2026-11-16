import type { ReactNode } from "react";
import type { Document } from "../api/documents";
import { formatDateTime, formatUpdated } from "../projects/time";
import styles from "./DocumentsSection.module.css";
import { FileTile } from "./FileTile";
import { formatSize } from "./fileRules";

function Meta({ document }: { document: Document }) {
  const replaced = document.updated_at !== document.created_at;
  const uploader = document.uploaded_by?.login ?? "a deleted account";
  return (
    <span className={styles.meta}>
      {replaced ? "Updated " : "Added "}
      <time
        dateTime={document.updated_at}
        title={formatDateTime(document.updated_at)}
      >
        {formatUpdated(document.updated_at)}
      </time>{" "}
      by {uploader}
    </span>
  );
}

export function DocumentRow({
  document,
  actions,
}: {
  document: Document;
  actions?: ReactNode;
}) {
  return (
    <li className={styles.row}>
      <FileTile name={document.name} />
      <span className={styles.name}>
        <span className={styles.fileName}>{document.name}</span>
        <Meta document={document} />
      </span>
      <span className={styles.size}>{formatSize(document.size)}</span>
      {actions !== undefined && (
        <span className={styles.actions}>{actions}</span>
      )}
    </li>
  );
}
