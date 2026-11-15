import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, type SubmitEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError, messageFor } from "../api/errors";
import { membersKey, removeMember, type Member } from "../api/members";
import type { Project } from "../api/projects";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { useToast } from "../ui/toast/useToast";
import styles from "./MemberDialog.module.css";

function mutationKey(project: Project) {
  return ["removeMember", project.id];
}

function isProjectGone(error: Error): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 422 ||
      (error.status === 404 && error.detail === "Project not found"))
  );
}

function isMemberGone(error: Error): boolean {
  return (
    error instanceof ApiError &&
    error.status === 404 &&
    error.detail === "Participant not found"
  );
}

function RemoveForm({
  project,
  member,
  textId,
  onClose,
  onRemoved,
}: {
  project: Project;
  member: Member;
  textId: string;
  onClose: () => void;
  onRemoved: () => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = membersKey(project.id);
  const sending = useRef(false);
  const mutation = useMutation({
    mutationKey: mutationKey(project),
    mutationFn: () => removeMember(project.id, member.id),
    onSettled: () => {
      sending.current = false;
    },
    onSuccess: () => {
      queryClient.setQueryData<Member[]>(key, (list) =>
        list?.filter(({ id }) => id !== member.id),
      );
      void queryClient.invalidateQueries({ queryKey: key });
      onRemoved();
      toast.success(`${member.login} removed from the project`);
    },
    onError: async (error) => {
      if (isMemberGone(error)) {
        void queryClient.invalidateQueries({ queryKey: key });
        onRemoved();
        toast.success(`${member.login} is no longer a member.`);
      } else if (isProjectGone(error)) {
        await navigate("/projects");
        queryClient.removeQueries({ queryKey: ["project", project.id] });
        queryClient.removeQueries({ queryKey: key });
        void queryClient.invalidateQueries({ queryKey: ["projects"] });
        toast.error("This project no longer exists.");
      }
    },
  });
  const failure =
    mutation.isError &&
    !isMemberGone(mutation.error) &&
    !isProjectGone(mutation.error)
      ? mutation.error instanceof ApiError && mutation.error.status === 403
        ? messageFor(mutation.error)
        : `Couldn't remove ${member.login}. Try again.`
      : null;

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sending.current) return;
    sending.current = true;
    mutation.reset();
    mutation.mutate();
  }

  return (
    <form noValidate onSubmit={submit}>
      <p id={textId} className={styles.text}>
        {member.login} loses access to <strong>{project.name}</strong> and its
        documents. You can invite them again later.
      </p>
      {failure && (
        <p role="alert" className={styles.alert}>
          {failure}
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
          Remove
        </Button>
      </div>
    </form>
  );
}

export function RemoveMemberDialog({
  project,
  member,
  onClose,
  onRemoved,
}: {
  project: Project;
  member: Member | null;
  onClose: () => void;
  onRemoved: () => void;
}) {
  const queryClient = useQueryClient();
  const textId = useId();
  return (
    <Dialog
      open={member !== null}
      role="alertdialog"
      title={member ? `Remove ${member.login}?` : ""}
      describedBy={textId}
      onClose={() => {
        if (
          queryClient.isMutating({ mutationKey: mutationKey(project) }) === 0
        ) {
          onClose();
        }
      }}
    >
      {member && (
        <RemoveForm
          key={member.id}
          project={project}
          member={member}
          textId={textId}
          onClose={onClose}
          onRemoved={onRemoved}
        />
      )}
    </Dialog>
  );
}
