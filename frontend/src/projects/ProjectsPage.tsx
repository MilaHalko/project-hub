import { useInfiniteQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Link, useSearchParams } from "react-router";
import { listProjects, type ProjectRole } from "../api/projects";
import { useMe } from "../auth/useMe";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import styles from "./ProjectsPage.module.css";
import { ProjectsSkeleton, ProjectsTable } from "./ProjectsTable";

const PAGE_SIZE = 20;

const TABS: { label: string; role?: ProjectRole }[] = [
  { label: "All" },
  { label: "Owned", role: "owner" },
  { label: "Shared with me", role: "participant" },
];

function roleFrom(value: string | null): ProjectRole | undefined {
  return value === "owner" || value === "participant" ? value : undefined;
}

function NewProjectButton() {
  return (
    <Button className={styles.newProject}>
      <Plus size={16} aria-hidden="true" />
      New project
    </Button>
  );
}

export function ProjectsPage() {
  const { data: user } = useMe();
  const [searchParams] = useSearchParams();
  const role = roleFrom(searchParams.get("role"));
  const projects = useInfiniteQuery({
    queryKey: ["projects", role ?? "all"],
    queryFn: ({ pageParam }) =>
      listProjects({ role, limit: PAGE_SIZE + 1, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _pages, lastOffset) =>
      lastPage.length > PAGE_SIZE ? lastOffset + PAGE_SIZE : undefined,
  });
  const rows =
    projects.data?.pages.flatMap((page) => page.slice(0, PAGE_SIZE)) ?? [];
  const empty = projects.isSuccess && rows.length === 0;
  const invitesToCreate = empty && role !== "participant";

  let content;
  if (projects.isPending) {
    content = <ProjectsSkeleton />;
  } else if (projects.isError) {
    content = (
      <div className={styles.error} role="alert">
        <p>Couldn&apos;t load your projects.</p>
        <Button
          variant="secondary"
          busy={projects.isFetching}
          onClick={() => {
            void projects.refetch();
          }}
        >
          Try again
        </Button>
      </div>
    );
  } else if (invitesToCreate) {
    content = (
      <div className={styles.empty}>
        <h2>Create your first project</h2>
        <p>
          A project keeps your documents and the people you work with in one
          place.
        </p>
        <NewProjectButton />
      </div>
    );
  } else if (empty) {
    content = (
      <div className={styles.empty}>
        <h2>Nothing shared with you yet</h2>
        <p>When someone invites you to a project, it shows up here.</p>
      </div>
    );
  } else {
    content = <ProjectsTable projects={rows} />;
  }

  return (
    <>
      <Banner
        tag={user ? `HI, ${user.login.toUpperCase()}` : "PROJECT_HUB"}
        title="Your projects"
      >
        <p>Projects you own and projects you were invited to.</p>
      </Banner>
      <div className={styles.toolbar}>
        <nav aria-label="Filter projects" className={styles.tabs}>
          {TABS.map((tab) => (
            <Link
              key={tab.label}
              to={tab.role ? `/projects?role=${tab.role}` : "/projects"}
              className={styles.tab}
              aria-current={tab.role === role ? "page" : undefined}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
        {!invitesToCreate && <NewProjectButton />}
      </div>
      <section
        aria-label="Projects"
        aria-busy={projects.isPending || undefined}
      >
        {content}
      </section>
    </>
  );
}
