import type { QueryClient } from "@tanstack/react-query";
import type { Document } from "../api/documents";

export function documentsQueryKey(projectId: string) {
  return ["documents", projectId];
}

export function documentsChanged(
  queryClient: QueryClient,
  projectId: string,
  update: (documents: Document[]) => Document[],
): void {
  queryClient.setQueryData<Document[]>(
    documentsQueryKey(projectId),
    (documents) => documents && update(documents),
  );
  void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
  void queryClient.invalidateQueries({ queryKey: ["projects"] });
}
