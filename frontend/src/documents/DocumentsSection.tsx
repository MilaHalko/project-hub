import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { listDocuments, type Document } from "../api/documents";
import type { ApiError } from "../api/errors";
import { Button } from "../ui/Button";
import { DocumentRow } from "./DocumentRow";
import styles from "./DocumentsSection.module.css";

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

export function documentsQueryKey(projectId: string) {
  return ["documents", projectId];
}

export function DocumentsSection({ projectId }: { projectId: string }) {
  const headingId = useId();
  const documents = useQuery<Document[], ApiError>({
    queryKey: documentsQueryKey(projectId),
    queryFn: () => listDocuments(projectId),
    staleTime: 30_000,
  });

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
        {documents.data.map((document) => (
          <DocumentRow key={document.id} document={document} />
        ))}
      </ul>
    );
  }

  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.heading}>
        Documents{" "}
        {documents.data !== undefined && (
          <span className={styles.count}>{documents.data.length}</span>
        )}
      </h2>
      {body}
    </section>
  );
}
