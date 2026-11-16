import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, type SubmitEvent } from "react";
import { deleteDocument, type Document } from "../api/documents";
import { ApiError } from "../api/errors";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { useToast } from "../ui/toast/useToast";
import styles from "./DeleteDocumentDialog.module.css";
import { DOCUMENT_GONE, documentsChanged } from "./documentsCache";
import { useWhatIsGone } from "./useWhatIsGone";

function mutationKey(document: Document) {
  return ["deleteDocument", document.id];
}

function DeleteForm({
  document,
  warningId,
  onClose,
  onRemoved,
}: {
  document: Document;
  warningId: string;
  onClose: () => void;
  onRemoved: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const sent = useRef(false);
  const whatIsGone = useWhatIsGone(document.project_id);

  function removed() {
    documentsChanged(queryClient, document.project_id, (documents) =>
      documents.filter(({ id }) => id !== document.id),
    );
    onClose();
    onRemoved();
  }

  const mutation = useMutation({
    mutationKey: mutationKey(document),
    mutationFn: () => deleteDocument(document.id),
    onSuccess: () => {
      removed();
      toast.success("Document deleted");
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 404) {
        const gone = await whatIsGone();
        if (gone === "project") return;
        if (gone === "document") {
          removed();
          toast.error(DOCUMENT_GONE);
          return;
        }
      }
      sent.current = false;
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sent.current) return;
    sent.current = true;
    mutation.reset();
    mutation.mutate();
  }

  return (
    <form noValidate onSubmit={submit}>
      <p id={warningId} className={styles.text}>
        This deletes <strong>{document.name}</strong> for everyone in the
        project. You can&apos;t undo this.
      </p>
      {mutation.isError && (
        <p role="alert" className={styles.alert}>
          Couldn&apos;t delete the document. Try again.
        </p>
      )}
      <div className={styles.buttons}>
        <Button
          variant="secondary"
          disabled={mutation.isPending}
          onClick={onClose}
        >
          Cancel
        </Button>
        <Button type="submit" variant="dangerSolid" busy={mutation.isPending}>
          Delete document
        </Button>
      </div>
    </form>
  );
}

export function DeleteDocumentDialog({
  open,
  document,
  onClose,
  onRemoved,
}: {
  open: boolean;
  document: Document;
  onClose: () => void;
  onRemoved: () => void;
}) {
  const queryClient = useQueryClient();
  const warningId = useId();
  return (
    <Dialog
      open={open}
      role="alertdialog"
      title="Delete this document?"
      describedBy={warningId}
      onClose={() => {
        if (
          queryClient.isMutating({ mutationKey: mutationKey(document) }) === 0
        ) {
          onClose();
        }
      }}
    >
      {open && (
        <DeleteForm
          document={document}
          warningId={warningId}
          onClose={onClose}
          onRemoved={onRemoved}
        />
      )}
    </Dialog>
  );
}
