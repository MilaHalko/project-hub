import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/errors";
import { membersKey } from "../api/members";
import { joinProject, type JoinResult } from "../api/shares";
import { useMe } from "../auth/useMe";
import { logOut } from "../auth/session";
import { RoleBadge } from "../projects/ProjectPage";
import { Banner } from "../ui/Banner";
import { Button, buttonClassName } from "../ui/Button";
import { clearJoinToken, readJoinToken } from "./joinToken";
import styles from "./JoinPage.module.css";

function isLinkInvalid(error: Error | null): boolean {
  return (
    error instanceof ApiError && (error.status === 404 || error.status === 422)
  );
}

function ProjectsLink() {
  return (
    <Link to="/projects" className={buttonClassName()}>
      Go to your projects
    </Link>
  );
}

function Result({ result }: { result: JoinResult }) {
  const { login, already_member, project } = result;
  return (
    <>
      <Banner
        tag={
          <span className={styles.tag}>
            <RoleBadge role={project.my_role} />
            {already_member ? "ALREADY A MEMBER" : "JOINED"}
          </span>
        }
        title={project.name}
      >
        {project.description && (
          <p className={styles.description}>{project.description}</p>
        )}
      </Banner>
      <p className={styles.result}>
        {already_member
          ? `You already have access as @${login}. The link was not used, so it still works for the person it was sent to.`
          : `You joined as @${login}. You are a participant now.`}
      </p>
      <Link to={`/projects/${project.id}`} className={buttonClassName()}>
        Open project
      </Link>
    </>
  );
}

export function JoinPage() {
  const [token] = useState(readJoinToken);
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const page = useRef<HTMLDivElement>(null);
  const joining = useRef(false);
  const mutation = useMutation<JoinResult, Error, string>({
    mutationFn: joinProject,
    onSuccess: (result) => {
      clearJoinToken();
      queryClient.setQueryData(["project", result.project.id], result.project);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({
        queryKey: membersKey(result.project.id),
      });
    },
    onError: (error) => {
      if (isLinkInvalid(error)) clearJoinToken();
    },
    onSettled: () => {
      joining.current = false;
    },
  });
  const finished = mutation.isSuccess || isLinkInvalid(mutation.error);

  useEffect(() => {
    if (finished) page.current?.querySelector("h1")?.focus();
  }, [finished]);

  if (token === null) {
    return (
      <div ref={page}>
        <Banner tag="INVITE" title="No invite link">
          <p>Open the link from your email again.</p>
        </Banner>
        <ProjectsLink />
      </div>
    );
  }

  if (mutation.isSuccess) {
    return (
      <div ref={page}>
        <Result result={mutation.data} />
      </div>
    );
  }

  if (isLinkInvalid(mutation.error)) {
    return (
      <div ref={page}>
        <Banner tag="LINK NOT VALID" title="This link doesn't work">
          <p>
            It may have expired, been used already, or been replaced by a newer
            link. Ask the project owner to send a new one.
          </p>
        </Banner>
        <ProjectsLink />
      </div>
    );
  }

  return (
    <div ref={page}>
      <Banner tag="INVITE" title="Join a project">
        {me && (
          <p>
            You are logged in as @{me.login}. Join with this account, or log out
            to use another one.
          </p>
        )}
      </Banner>
      {mutation.isError && (
        <p role="alert" className={styles.alert}>
          Couldn&apos;t join the project. Try again.
        </p>
      )}
      <div className={styles.actions}>
        <Button
          busy={mutation.isPending}
          onClick={() => {
            if (joining.current) return;
            joining.current = true;
            mutation.mutate(token);
          }}
        >
          Join project
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            void logOut();
          }}
        >
          Log out
        </Button>
      </div>
    </div>
  );
}
