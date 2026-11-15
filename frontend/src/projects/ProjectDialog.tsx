import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type SubmitEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError, fieldErrors } from "../api/errors";
import { createProject } from "../api/projects";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Field } from "../ui/Field";
import { TextAreaField } from "../ui/TextAreaField";
import { useToast } from "../ui/toast/useToast";
import styles from "./ProjectDialog.module.css";
import {
  characterCount,
  checkProject,
  type ProjectErrors,
} from "./projectRules";

const FAILED = "Couldn't create the project. Try again.";

function serverErrors(error: Error | null): {
  fields: ProjectErrors;
  form: string | null;
} {
  if (error === null) return { fields: {}, form: null };
  if (error instanceof ApiError && error.status === 422) {
    const { fields, form } = fieldErrors(error);
    const known = fields.name !== undefined || fields.description !== undefined;
    return {
      fields: { name: fields.name, description: fields.description },
      form: known ? form : (form ?? FAILED),
    };
  }
  return { fields: {}, form: FAILED };
}

const CREATE_KEY = ["createProject"];

function ProjectForm({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [edited, setEdited] = useState({ name: false, description: false });
  const nameInput = useRef<HTMLInputElement>(null);
  const descriptionInput = useRef<HTMLTextAreaElement>(null);
  const mutation = useMutation({
    mutationKey: CREATE_KEY,
    mutationFn: createProject,
    onSuccess: async (created) => {
      queryClient.setQueryData(["project", created.id], created);
      toast.success("Project created");
      onClose();
      await navigate(`/projects/${encodeURIComponent(created.id)}`);
      void queryClient.resetQueries({ queryKey: ["projects"] });
    },
  });

  useEffect(() => {
    nameInput.current?.focus();
  }, []);

  const client = submitted ? checkProject({ name, description }) : {};
  const server = serverErrors(mutation.error);
  const errors: ProjectErrors = {
    name: client.name ?? (edited.name ? undefined : server.fields.name),
    description:
      client.description ??
      (edited.description ? undefined : server.fields.description),
  };

  function focusFirstInvalid(found: ProjectErrors) {
    if (found.name) nameInput.current?.focus();
    else if (found.description) descriptionInput.current?.focus();
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    setSubmitted(true);
    setEdited({ name: false, description: false });
    mutation.reset();
    const found = checkProject({ name, description });
    if (found.name || found.description) {
      focusFirstInvalid(found);
      return;
    }
    mutation.mutate(
      { name: name.trim(), description },
      {
        onError: (error) => {
          setEdited({ name: false, description: false });
          focusFirstInvalid(serverErrors(error).fields);
        },
      },
    );
  }

  return (
    <form noValidate onSubmit={submit}>
      <Field
        ref={nameInput}
        label="Name"
        name="name"
        autoComplete="off"
        value={name}
        error={errors.name}
        onChange={(event) => {
          setName(event.target.value);
          setEdited((was) => ({ ...was, name: true }));
        }}
      />
      <TextAreaField
        ref={descriptionInput}
        label="Description (optional)"
        name="description"
        value={description}
        error={errors.description}
        hint={`${String(characterCount(description))} / 2000`}
        onChange={(event) => {
          setDescription(event.target.value);
          setEdited((was) => ({ ...was, description: true }));
        }}
      />
      {server.form !== null && (
        <p role="alert" className={styles.alert}>
          {server.form}
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
        <Button type="submit" busy={mutation.isPending}>
          Create project
        </Button>
      </div>
    </form>
  );
}

export function ProjectDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  return (
    <Dialog
      open={open}
      title="New project"
      onClose={() => {
        if (queryClient.isMutating({ mutationKey: CREATE_KEY }) === 0) {
          onClose();
        }
      }}
    >
      {open && <ProjectForm onClose={onClose} />}
    </Dialog>
  );
}
