import {
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { useId, useRef, type SubmitEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError } from "../api/errors";
import { membersKey, removeMember } from "../api/members";
import type { Project } from "../api/projects";
import { useMe } from "../auth/useMe";
import { withoutProject } from "../projects/projectPages";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { useToast } from "../ui/toast/useToast";
import styles from "./MemberDialog.module.css";

function mutationKey(project: Project) {
  return ["leaveProject", project.id];
}

function lostAccess(error: Error): boolean {
  return (
    error instanceof ApiError && (error.status === 404 || error.status === 422)
  );
}

function failureMessage(error: Error): string {
  return error instanceof ApiError && error.status === 409
    ? "The owner can't leave the project."
    : "Couldn't leave the project. Try again.";
}

function LeaveForm({
  project,
  textId,
  onClose,
}: {
  project: Project;
  textId: string;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: me } = useMe();
  const sending = useRef(false);

  async function forgetProject() {
    await navigate("/projects");
    queryClient.removeQueries({ queryKey: ["project", project.id] });
    queryClient.removeQueries({ queryKey: membersKey(project.id) });
    queryClient.setQueriesData<InfiniteData<Project[]>>(
      { queryKey: ["projects"] },
      (data) => data && withoutProject(data, project.id),
    );
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
  }

  const mutation = useMutation({
    mutationKey: mutationKey(project),
    mutationFn: (myId: string) => removeMember(project.id, myId),
    onSettled: () => {
      sending.current = false;
    },
    onSuccess: async () => {
      await forgetProject();
      toast.success(`You left ${project.name}`);
    },
    onError: async (error) => {
      if (!lostAccess(error)) return;
      await forgetProject();
      toast.error("You no longer have access to this project.");
    },
  });
  const failed = mutation.isError && !lostAccess(mutation.error);

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (me === undefined || sending.current) return;
    sending.current = true;
    mutation.reset();
    mutation.mutate(me.id);
  }

  return (
    <form noValidate onSubmit={submit}>
      <p id={textId} className={styles.text}>
        You lose access to <strong>{project.name}</strong> and its documents.
        Only the owner can invite you back.
      </p>
      {failed && (
        <p role="alert" className={styles.alert}>
          {failureMessage(mutation.error)}
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
        <Button
          type="submit"
          variant="dangerSolid"
          busy={me === undefined || mutation.isPending}
        >
          Leave project
        </Button>
      </div>
    </form>
  );
}

export function LeaveProjectDialog({
  open,
  project,
  onClose,
}: {
  open: boolean;
  project: Project;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const textId = useId();
  return (
    <Dialog
      open={open}
      role="alertdialog"
      title="Leave this project?"
      describedBy={textId}
      onClose={() => {
        if (
          queryClient.isMutating({ mutationKey: mutationKey(project) }) === 0
        ) {
          onClose();
        }
      }}
    >
      {open && (
        <LeaveForm project={project} textId={textId} onClose={onClose} />
      )}
    </Dialog>
  );
}
