import type { Document } from "../api/documents";
import styles from "./DocumentsSection.module.css";
import { FileTile } from "./FileTile";
import { usePreviewUrl } from "./usePreviewUrl";

export function DocumentThumbnail({ document }: { document: Document }) {
  const url = usePreviewUrl(document);
  if (url === null) return <FileTile name={document.name} />;
  return (
    <img
      className={styles.thumbnail}
      src={url}
      alt={`Preview of ${document.name}`}
    />
  );
}
