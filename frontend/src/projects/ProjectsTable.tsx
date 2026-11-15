import { Link } from "react-router";
import type { Project } from "../api/projects";
import { ownerLabel } from "./ownerLabel";
import styles from "./ProjectsTable.module.css";
import { formatDateTime, formatUpdated } from "./time";

export function ProjectsTable({ projects }: { projects: Project[] }) {
  return (
    <div className={styles.frame}>
      <table className={styles.table}>
        <thead className={styles.head}>
          <tr>
            <th scope="col">Project</th>
            <th scope="col" className={styles.roleColumn}>
              Role
            </th>
            <th scope="col" className={styles.ownerColumn}>
              Owner
            </th>
            <th scope="col" className={styles.updatedColumn}>
              Updated
            </th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id} className={styles.row}>
              <td className={styles.project}>
                <Link
                  to={`/projects/${encodeURIComponent(project.id)}`}
                  className={styles.name}
                >
                  {project.name}
                </Link>
                {project.description ? (
                  <span className={styles.description}>
                    {project.description}
                  </span>
                ) : (
                  <span className={[styles.description, styles.none].join(" ")}>
                    No description
                  </span>
                )}
              </td>
              <td className={styles.role}>
                <span
                  className={
                    project.my_role === "owner"
                      ? styles.ownerBadge
                      : styles.participantBadge
                  }
                >
                  {project.my_role === "owner" ? "Owner" : "Participant"}
                </span>
              </td>
              <td className={styles.owner}>{ownerLabel(project)}</td>
              <td className={styles.updated}>
                <span className={styles.cardOnly}>, updated </span>
                <time
                  dateTime={project.updated_at}
                  title={formatDateTime(project.updated_at)}
                >
                  {formatUpdated(project.updated_at)}
                </time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProjectsSkeleton() {
  return (
    <div className={styles.frame} aria-hidden="true">
      <div className={styles.skeletonHead} />
      {["46%", "38%", "52%"].map((width) => (
        <div key={width} className={styles.skeletonRow}>
          <span className={styles.skeletonText}>
            <span style={{ width }} />
            <span />
          </span>
          <span className={styles.skeletonBadge} />
          <span className={styles.skeletonMeta} />
          <span className={styles.skeletonMeta} />
        </div>
      ))}
    </div>
  );
}
