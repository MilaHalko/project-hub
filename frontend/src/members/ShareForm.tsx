import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type SubmitEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError } from "../api/errors";
import { membersKey } from "../api/members";
import type { Project } from "../api/projects";
import { shareProject, type ShareLink } from "../api/shares";
import { formatDateTime } from "../projects/time";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";
import { useToast } from "../ui/toast/useToast";
import styles from "./MembersPanel.module.css";

const MAX_EMAIL = 254;
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+$/;

function checkEmail(email: string): string | null {
  if (email === "") return "Enter an email address.";
  if (!EMAIL_SHAPE.test(email)) {
    return "Enter an address like name@example.com.";
  }
  if (email.length > MAX_EMAIL) return "Use 254 characters or fewer.";
  return null;
}

function failureMessage(error: Error): string {
  const failed = "Couldn't send the link. Try again.";
  if (!(error instanceof ApiError)) return failed;
  const { status, detail } = error;
  if (status === 422) return "Check the email address and try again.";
  if (status === 429) {
    return "This project already has 10 unused links. Wait until one is used or expires, or invite by login.";
  }
  if (status === 503 && detail === "Email sharing is not configured") {
    return "Email isn't set up on this server. Invite people by login instead.";
  }
  if (status === 503 && detail === "Email could not be sent") {
    return "Couldn't send the email. Try again later.";
  }
  if (status === 403) return "Only the owner can share the project.";
  return failed;
}

function isProjectGone(error: Error): boolean {
  return (
    error instanceof ApiError &&
    error.status === 404 &&
    error.detail === "Project not found"
  );
}

export function ShareForm({ project }: { project: Project }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const field = useRef<HTMLInputElement>(null);
  const [typed, setTyped] = useState("");
  const [checked, setChecked] = useState(false);
  const sending = useRef(false);
  const mutation = useMutation<ShareLink, Error, string>({
    mutationFn: (email) => shareProject(project.id, email),
    onSuccess: (link) => {
      setTyped("");
      setChecked(false);
      field.current?.focus();
      toast.success(
        `Link sent to ${link.email}. It works until ${formatDateTime(link.expires_at)}.`,
      );
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
  const email = typed.trim();
  const checkError = checked ? checkEmail(email) : null;
  const apiError =
    mutation.isError && !isProjectGone(mutation.error)
      ? failureMessage(mutation.error)
      : null;
  const error = checkError ?? apiError;

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sending.current) return;
    setChecked(true);
    if (checkEmail(email) !== null) {
      field.current?.focus();
      return;
    }
    sending.current = true;
    mutation.mutate(email);
  }

  return (
    <form className={styles.share} noValidate onSubmit={submit}>
      <Field
        ref={field}
        label="Send a link by email"
        name="email"
        type="email"
        inputMode="email"
        autoComplete="off"
        hint="The link works once, for 7 days."
        value={typed}
        error={error ?? undefined}
        onChange={(event) => {
          setTyped(event.target.value);
          if (!mutation.isPending) mutation.reset();
        }}
      />
      <Button type="submit" variant="secondary" wide busy={mutation.isPending}>
        Send link
      </Button>
    </form>
  );
}
