import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef } from "react";
import { listDocuments, type Document } from "../api/documents";
import type { ApiError } from "../api/errors";
import { Button } from "../ui/Button";
import { DocumentActions } from "./DocumentActions";
import { DocumentRow } from "./DocumentRow";
import { documentsQueryKey } from "./documentsCache";
import styles from "./DocumentsSection.module.css";
import { isFull, type Space } from "./space";
import { SpaceUsed } from "./SpaceUsed";
import { UploadZone } from "./UploadZone";

function DocumentsSkeleton() {
  return (
    <div
      className={styles.list}
      role="status"
      aria-busy="true"
      aria-label="Loading documents"
    >
      {["62%", "48%", "56%"].map((width) => (
        <div key={width} className={styles.skeletonRow}>
          <span className={styles.skeletonTile} />
          <span className={styles.skeletonText} style={{ width }} />
          <span className={styles.skeletonText} />
        </div>
      ))}
    </div>
  );
}

export function DocumentsSection({
  projectId,
  space = null,
}: {
  projectId: string;
  space?: Space | null;
}) {
  const headingId = useId();
  const section = useRef<HTMLElement>(null);
  const focusAfterRemoval = useRef<number | null>(null);
  const documents = useQuery<Document[], ApiError>({
    queryKey: documentsQueryKey(projectId),
    queryFn: () => listDocuments(projectId),
    staleTime: 30_000,
  });

  useEffect(() => {
    const removedAt = focusAfterRemoval.current;
    if (removedAt === null) return;
    focusAfterRemoval.current = null;
    const downloads = section.current?.querySelectorAll<HTMLElement>(
      'button[aria-label^="Download "]',
    );
    const next =
      downloads?.[Math.min(removedAt, downloads.length - 1)] ??
      section.current?.querySelector<HTMLElement>(
        'input[type="file"][multiple]',
      );
    next?.focus();
  }, [documents.data]);

  let body;
  if (documents.isPending) {
    body = <DocumentsSkeleton />;
  } else if (documents.isError) {
    body = (
      <div className={styles.error} role="alert">
        <p>Couldn&apos;t load the documents.</p>
        <Button
          variant="secondary"
          busy={documents.isFetching}
          onClick={() => {
            void documents.refetch();
          }}
        >
          Try again
        </Button>
      </div>
    );
  } else if (documents.data.length === 0) {
    body = (
      <div className={styles.empty}>
        <p className={styles.emptyTitle}>No documents yet</p>
        <p>Upload the first one above.</p>
      </div>
    );
  } else {
    body = (
      <ul className={styles.list} aria-labelledby={headingId}>
        {documents.data.map((document, index) => (
          <DocumentRow
            key={document.id}
            document={document}
            actions={
              <DocumentActions
                document={document}
                onRemoved={() => {
                  focusAfterRemoval.current = index;
                }}
              />
            }
          />
        ))}
      </ul>
    );
  }

  return (
    <section
      ref={section}
      className={styles.section}
      aria-labelledby={headingId}
    >
      <div className={styles.head}>
        <h2 id={headingId} className={styles.heading}>
          Documents{" "}
          {documents.data !== undefined && (
            <span className={styles.count}>{documents.data.length}</span>
          )}
        </h2>
        {space !== null && <SpaceUsed space={space} />}
      </div>
      <UploadZone projectId={projectId} full={isFull(space)} />
      {body}
    </section>
  );
}
