import { useEffect, useState } from "react";
import { previewDocument, type Document } from "../api/documents";

const PREVIEW_TYPES = new Set(["image/jpeg", "image/png"]);
const RETRY_DELAY_MS = 2000;
const MAX_RETRIES = 5;

export function hasPreview(document: Document): boolean {
  return PREVIEW_TYPES.has(document.content_type);
}

export function usePreviewUrl(document: Document): string | null {
  const [url, setUrl] = useState<string | null>(null);
  const { id, updated_at: updatedAt } = document;
  const wanted = hasPreview(document);

  useEffect(() => {
    if (!wanted) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let objectUrl: string | undefined;

    function attempt(retries: number) {
      previewDocument(id).then(
        (blob) => {
          if (stopped) return;
          objectUrl = URL.createObjectURL(blob);
          setUrl(objectUrl);
        },
        () => {
          if (stopped || retries >= MAX_RETRIES) return;
          timer = setTimeout(() => {
            attempt(retries + 1);
          }, RETRY_DELAY_MS);
        },
      );
    }
    attempt(0);

    return () => {
      stopped = true;
      clearTimeout(timer);
      if (objectUrl !== undefined) URL.revokeObjectURL(objectUrl);
      setUrl(null);
    };
  }, [id, updatedAt, wanted]);

  return url;
}
