import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type SubmitEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError, fieldErrors } from "../api/errors";
import { inviteMember, membersKey, type Member } from "../api/members";
import type { Project } from "../api/projects";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";
import { useToast } from "../ui/toast/useToast";
import styles from "./MembersPanel.module.css";

const MAX_LOGIN = 32;

function checkLogin(login: string): string | null {
  if (login === "") return "Enter a login.";
  if (login.length > MAX_LOGIN) return "Use 32 characters or fewer.";
  return null;
}

function failureMessage(error: Error, login: string): string {
  const failed = `Couldn't invite ${login}. Try again.`;
  if (!(error instanceof ApiError)) return failed;
  const { status, detail } = error;
  if (status === 404 && detail === "User not found") {
    return "No user with that login. Logins are case-sensitive.";
  }
  if (
    status === 409 &&
    detail === "User is already a participant of this project"
  ) {
    return `${login} is already a member.`;
  }
  if (status === 409 && detail === "You already own this project") {
    return "That's your login. You already own this project.";
  }
  if (status === 403) return "Only the owner can invite people.";
  if (status === 422) {
    return fieldErrors(error).fields.user ?? "Check the login and try again.";
  }
  return failed;
}

function isProjectGone(error: Error): boolean {
  return (
    error instanceof ApiError &&
    error.status === 404 &&
    error.detail === "Project not found"
  );
}

export function InviteForm({ project }: { project: Project }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const field = useRef<HTMLInputElement>(null);
  const [typed, setTyped] = useState("");
  const [checked, setChecked] = useState(false);
  const sending = useRef(false);
  const mutation = useMutation<Member, Error, string>({
    mutationFn: (login) => inviteMember(project.id, login),
    onSuccess: (member) => {
      queryClient.setQueryData<Member[]>(membersKey(project.id), (list) =>
        list === undefined || list.some(({ id }) => id === member.id)
          ? list
          : [...list, member],
      );
      void queryClient.invalidateQueries({ queryKey: membersKey(project.id) });
      setTyped("");
      setChecked(false);
      field.current?.focus();
      toast.success(`${member.login} added to the project`);
    },
    onSettled: () => {
      sending.current = false;
    },
    onError: async (error) => {
      if (!isProjectGone(error)) {
        field.current?.focus();
        return;
      }
      await navigate("/projects");
      queryClient.removeQueries({ queryKey: ["project", project.id] });
      queryClient.removeQueries({ queryKey: membersKey(project.id) });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.error("This project no longer exists.");
    },
  });
  const login = typed.trim();
  const checkError = checked ? checkLogin(login) : null;
  const apiError =
    mutation.isError && !isProjectGone(mutation.error)
      ? failureMessage(mutation.error, mutation.variables)
      : null;
  const error = checkError ?? apiError;

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sending.current) return;
    setChecked(true);
    if (checkLogin(login) !== null) {
      field.current?.focus();
      return;
    }
    sending.current = true;
    mutation.mutate(login);
  }

  return (
    <form className={styles.invite} noValidate onSubmit={submit}>
      <Field
        ref={field}
        label="Invite by login"
        name="login"
        autoComplete="off"
        value={typed}
        error={error ?? undefined}
        onChange={(event) => {
          setTyped(event.target.value);
          if (!mutation.isPending) mutation.reset();
        }}
      />
      <Button type="submit" wide busy={mutation.isPending}>
        Invite
      </Button>
    </form>
  );
}
