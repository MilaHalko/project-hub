import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ApiError } from "../api/errors";
import { getProject, type Project } from "../api/projects";
import { Banner } from "../ui/Banner";
import { Button, buttonClassName } from "../ui/Button";
import { DeleteProjectDialog } from "./DeleteProjectDialog";
import { ProjectDialog } from "./ProjectDialog";
import styles from "./ProjectPage.module.css";
import { ownerLabel } from "./ownerLabel";
import { formatDate, formatDateTime, formatUpdated } from "./time";

function isNotFound(error: unknown): boolean {
  return (
    error instanceof ApiError && (error.status === 404 || error.status === 422)
  );
}

function Crumbs({ name }: { name?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={styles.crumbs}>
      <Link to="/projects">Projects</Link>
      {name !== undefined && (
        <>
          <span aria-hidden="true"> / </span>
          <span aria-current="page">{name}</span>
        </>
      )}
    </nav>
  );
}

function RoleBadge({ role }: { role: Project["my_role"] }) {
  return (
    <span
      className={role === "owner" ? styles.ownerBadge : styles.participantBadge}
    >
      {role === "owner" ? "Owner" : "Participant"}
    </span>
  );
}

function Details({ project }: { project: Project }) {
  return (
    <dl className={styles.details}>
      <div>
        <dt>Owner</dt>
        <dd>{ownerLabel(project)}</dd>
      </div>
      <div>
        <dt>Created</dt>
        <dd>{formatDate(project.created_at)}</dd>
      </div>
      <div>
        <dt>Updated</dt>
        <dd title={formatDateTime(project.updated_at)}>
          {formatUpdated(project.updated_at)}
        </dd>
      </div>
    </dl>
  );
}

function ProjectSkeleton() {
  return (
    <div
      className={styles.skeleton}
      role="status"
      aria-busy="true"
      aria-label="Loading project"
    >
      <span className={styles.skeletonBadge} />
      <span className={styles.skeletonTitle} />
      <span className={styles.skeletonLine} />
    </div>
  );
}

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const project = useQuery<Project, ApiError>({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
    staleTime: 30_000,
  });
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const name = project.data?.name;

  useEffect(() => {
    if (name === undefined) return;
    document.title = `${name} — Project Hub`;
    return () => {
      document.title = "Project Hub";
    };
  }, [name]);

  if (project.isPending) {
    return (
      <>
        <Crumbs />
        <ProjectSkeleton />
      </>
    );
  }

  if (project.isError && isNotFound(project.error)) {
    return (
      <>
        <Crumbs />
        <Banner tag="ERROR 404" title="Project not found">
          <p>It may have been deleted, or you don&apos;t have access to it.</p>
        </Banner>
        <Link to="/projects" className={buttonClassName()}>
          Back to projects
        </Link>
      </>
    );
  }

  if (project.isError) {
    return (
      <>
        <Crumbs />
        <div className={styles.error} role="alert">
          <p>Couldn&apos;t load the project.</p>
          <Button
            variant="secondary"
            busy={project.isFetching}
            onClick={() => {
              void project.refetch();
            }}
          >
            Try again
          </Button>
        </div>
      </>
    );
  }

  const data = project.data;
  return (
    <>
      <Crumbs name={data.name} />
      <Banner
        tag={<RoleBadge role={data.my_role} />}
        title={data.name}
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setEditing(true);
              }}
            >
              Edit
            </Button>
            {data.my_role === "owner" && (
              <Button
                variant="danger"
                onClick={() => {
                  setDeleting(true);
                }}
              >
                Delete project
              </Button>
            )}
          </>
        }
      >
        {data.description && (
          <p className={styles.description}>{data.description}</p>
        )}
      </Banner>
      <Details project={data} />
      <ProjectDialog
        open={editing}
        project={data}
        onClose={() => {
          setEditing(false);
        }}
      />
      <DeleteProjectDialog
        open={deleting}
        project={data}
        onClose={() => {
          setDeleting(false);
        }}
      />
    </>
  );
}
