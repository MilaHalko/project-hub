import {
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { useId, useState, type SubmitEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError, messageFor } from "../api/errors";
import { deleteProject, type Project } from "../api/projects";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Field } from "../ui/Field";
import { useToast } from "../ui/toast/useToast";
import styles from "./DeleteProjectDialog.module.css";
import { withoutProject } from "./projectPages";

const DELETE_FAILED = "Couldn't delete the project. Try again.";

function mutationKey(project: Project) {
  return ["deleteProject", project.id];
}

function failureMessage(error: Error): string {
  return error instanceof ApiError && error.status === 403
    ? messageFor(error)
    : DELETE_FAILED;
}

function DeleteForm({
  project,
  warningId,
  onClose,
}: {
  project: Project;
  warningId: string;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [typed, setTyped] = useState("");
  const mutation = useMutation({
    mutationKey: mutationKey(project),
    mutationFn: () => deleteProject(project.id),
    onSuccess: async () => {
      queryClient.setQueriesData<InfiniteData<Project[]>>(
        { queryKey: ["projects"] },
        (data) => data && withoutProject(data, project.id),
      );
      await navigate("/projects");
      queryClient.removeQueries({ queryKey: ["project", project.id] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project deleted");
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 404) {
        await navigate("/projects");
        queryClient.removeQueries({ queryKey: ["project", project.id] });
        void queryClient.invalidateQueries({ queryKey: ["projects"] });
        toast.error("This project no longer exists.");
      }
    },
  });
  const matches = typed.trim() === project.name;
  const failed =
    mutation.error !== null &&
    !(mutation.error instanceof ApiError && mutation.error.status === 404);

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!matches || mutation.isPending) return;
    mutation.reset();
    mutation.mutate();
  }

  return (
    <form noValidate onSubmit={submit}>
      <p id={warningId} className={styles.text}>
        This deletes <strong>{project.name}</strong> with all its documents and
        removes everyone&apos;s access. You can&apos;t undo this.
      </p>
      <Field
        label="Type the project name to confirm"
        name="confirm"
        autoComplete="off"
        value={typed}
        onChange={(event) => {
          setTyped(event.target.value);
        }}
      />
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
          disabled={!matches}
          busy={mutation.isPending}
        >
          Delete project
        </Button>
      </div>
    </form>
  );
}

export function DeleteProjectDialog({
  open,
  project,
  onClose,
}: {
  open: boolean;
  project: Project;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const warningId = useId();
  return (
    <Dialog
      open={open}
      role="alertdialog"
      title="Delete this project?"
      describedBy={warningId}
      onClose={() => {
        if (
          queryClient.isMutating({ mutationKey: mutationKey(project) }) === 0
        ) {
          onClose();
        }
      }}
    >
      {open && (
        <DeleteForm project={project} warningId={warningId} onClose={onClose} />
      )}
    </Dialog>
  );
}
