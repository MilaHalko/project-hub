import { useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { ApiError } from "../api/errors";
import { membersKey } from "../api/members";
import type { Project } from "../api/projects";
import { documentsQueryKey } from "../documents/documentsCache";
import { withoutProject } from "./projectPages";

export const LOST_ACCESS = "You no longer have access to this project.";

export function lostAccess(error: unknown): boolean {
  return (
    error instanceof ApiError && (error.status === 404 || error.status === 422)
  );
}

export function useForgetProject(projectId: string): () => Promise<void> {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return async () => {
    await navigate("/projects");
    queryClient.removeQueries({ queryKey: ["project", projectId] });
    queryClient.removeQueries({ queryKey: membersKey(projectId) });
    queryClient.removeQueries({ queryKey: documentsQueryKey(projectId) });
    queryClient.setQueriesData<InfiniteData<Project[]>>(
      { queryKey: ["projects"] },
      (data) => data && withoutProject(data, projectId),
    );
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
  };
}
