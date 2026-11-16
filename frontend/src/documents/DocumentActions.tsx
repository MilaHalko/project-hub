import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import { useId, useRef, useState } from "react";
import {
  downloadDocument,
  replaceDocument,
  type Document,
} from "../api/documents";
import { ApiError } from "../api/errors";
import { Button, buttonClassName } from "../ui/Button";
import { useToast } from "../ui/toast/useToast";
import { DeleteDocumentDialog } from "./DeleteDocumentDialog";
import styles from "./DocumentsSection.module.css";
import {
  DOCUMENT_GONE,
  documentsChanged,
  reloadDocuments,
} from "./documentsCache";
import { checkFile, uploadErrorMessage } from "./fileRules";
import { saveBlob } from "./saveBlob";

function isGone(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function DocumentActions({
  document,
  onRemoved,
}: {
  document: Document;
  onRemoved: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const inputId = useId();
  const downloading = useRef(false);
  const [deleting, setDeleting] = useState(false);

  function gone() {
    toast.error(DOCUMENT_GONE);
    reloadDocuments(queryClient, document.project_id);
  }

  const download = useMutation({
    mutationFn: () => downloadDocument(document.id),
    onSettled: () => {
      downloading.current = false;
    },
    onSuccess: (blob) => {
      saveBlob(blob, document.name);
    },
    onError: (error) => {
      if (isGone(error)) {
        gone();
        return;
      }
      toast.error(`Couldn't download ${document.name}. Try again.`);
    },
  });

  const replace = useMutation({
    mutationFn: (file: File) => replaceDocument(document.id, file),
    onSuccess: (replaced) => {
      documentsChanged(queryClient, document.project_id, (documents) =>
        documents.map((item) => (item.id === replaced.id ? replaced : item)),
      );
      toast.success("File replaced");
    },
    onError: (error, file) => {
      if (isGone(error)) {
        gone();
        return;
      }
      toast.error(uploadErrorMessage(error, file.name));
    },
  });

  function choose(file: File | undefined) {
    if (file === undefined || replace.isPending) return;
    const refused = checkFile(file);
    if (refused !== null) {
      toast.error(refused);
      return;
    }
    replace.mutate(file);
  }

  return (
    <>
      {replace.isPending ? (
        <span className={styles.replacing}>
          <LoaderCircle className={styles.spinner} size={14} aria-hidden />
          Replacing…
        </span>
      ) : (
        <Button
          variant="secondary"
          busy={download.isPending}
          aria-label={`Download ${document.name}`}
          onClick={(event) => {
            if (downloading.current || event.detail > 1) return;
            downloading.current = true;
            download.mutate();
          }}
        >
          Download
        </Button>
      )}
      <input
        id={inputId}
        className={styles.input}
        type="file"
        accept=".pdf,.docx"
        aria-label={`Replace ${document.name}`}
        onChange={(event) => {
          choose(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      {!replace.isPending && (
        <>
          <label
            htmlFor={inputId}
            className={buttonClassName({ variant: "secondary" })}
          >
            Replace
          </label>
          <Button
            variant="danger"
            aria-label={`Delete ${document.name}`}
            onClick={() => {
              setDeleting(true);
            }}
          >
            Delete
          </Button>
        </>
      )}
      <DeleteDocumentDialog
        open={deleting}
        document={document}
        onClose={() => {
          setDeleting(false);
        }}
        onRemoved={onRemoved}
      />
    </>
  );
}
