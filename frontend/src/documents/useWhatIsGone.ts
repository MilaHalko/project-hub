import { useQueryClient } from "@tanstack/react-query";
import { getProject, type Project } from "../api/projects";
import {
  LOST_ACCESS,
  lostAccess,
  useForgetProject,
} from "../projects/useForgetProject";
import { useToast } from "../ui/toast/useToast";

export function useWhatIsGone(
  projectId: string,
): () => Promise<"document" | "project" | "unknown"> {
  const queryClient = useQueryClient();
  const forgetProject = useForgetProject(projectId);
  const toast = useToast();
  return async () => {
    let project: Project;
    try {
      project = await getProject(projectId);
    } catch (error) {
      if (!lostAccess(error)) return "unknown";
      await forgetProject();
      toast.error(LOST_ACCESS);
      return "project";
    }
    queryClient.setQueryData(["project", projectId], project);
    return "document";
  };
}
