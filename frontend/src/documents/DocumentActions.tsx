import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { downloadDocument, type Document } from "../api/documents";
import { ApiError } from "../api/errors";
import { Button } from "../ui/Button";
import { useToast } from "../ui/toast/useToast";
import { DOCUMENT_GONE, reloadDocuments } from "./documentsCache";
import { saveBlob } from "./saveBlob";

function isGone(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function DocumentActions({ document }: { document: Document }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const working = useRef(false);
  const download = useMutation({
    mutationFn: () => downloadDocument(document.id),
    onSettled: () => {
      working.current = false;
    },
    onSuccess: (blob) => {
      saveBlob(blob, document.name);
    },
    onError: (error) => {
      if (isGone(error)) {
        toast.error(DOCUMENT_GONE);
        reloadDocuments(queryClient, document.project_id);
        return;
      }
      toast.error(`Couldn't download ${document.name}. Try again.`);
    },
  });

  return (
    <Button
      variant="secondary"
      busy={download.isPending}
      aria-label={`Download ${document.name}`}
      onClick={(event) => {
        if (working.current || event.detail > 1) return;
        working.current = true;
        download.mutate();
      }}
    >
      Download
    </Button>
  );
}
