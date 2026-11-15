import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import type { ApiError } from "../api/errors";
import { listMembers, membersKey, type Member } from "../api/members";
import type { Project } from "../api/projects";
import { useMe } from "../auth/useMe";
import { Avatar } from "../ui/avatar/Avatar";
import { Button } from "../ui/Button";
import { InviteForm } from "./InviteForm";
import styles from "./MembersPanel.module.css";

function MemberRow({ member, isMe }: { member: Member; isMe: boolean }) {
  return (
    <li className={styles.row}>
      <Avatar userId={member.id} size={28} />
      <span className={styles.login}>
        {member.login}
        {isMe && <span className={styles.you}> (you)</span>}
      </span>
      <span
        className={
          member.role === "owner" ? styles.ownerBadge : styles.participantBadge
        }
      >
        {member.role === "owner" ? "Owner" : "Participant"}
      </span>
    </li>
  );
}

function MembersSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading members">
      {[0, 1, 2].map((row) => (
        <span key={row} className={styles.skeletonRow}>
          <span className={styles.skeletonAvatar} />
          <span className={styles.skeletonLine} />
        </span>
      ))}
    </div>
  );
}

export function MembersPanel({ project }: { project: Project }) {
  const headingId = useId();
  const { data: me } = useMe();
  const members = useQuery<Member[], ApiError>({
    queryKey: membersKey(project.id),
    queryFn: () => listMembers(project.id),
    staleTime: 30_000,
  });

  return (
    <section className={styles.panel} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.heading} tabIndex={-1}>
        Members
        {members.data && (
          <>
            {" "}
            <span className={styles.count}>{members.data.length}</span>
          </>
        )}
      </h2>
      {members.isPending && <MembersSkeleton />}
      {members.isError && (
        <div className={styles.error} role="alert">
          <p>Couldn&apos;t load the members.</p>
          <Button
            variant="secondary"
            busy={members.isFetching}
            onClick={() => {
              void members.refetch();
            }}
          >
            Try again
          </Button>
        </div>
      )}
      {members.data && (
        <ul className={styles.list}>
          {members.data.map((member) => (
            <MemberRow
              key={member.id}
              member={member}
              isMe={member.id === me?.id}
            />
          ))}
        </ul>
      )}
      {project.my_role === "owner" && (
        <>
          {members.data?.every(({ role }) => role === "owner") && (
            <p className={styles.hint}>
              Only you so far. Invite people by their login.
            </p>
          )}
          <InviteForm project={project} />
        </>
      )}
    </section>
  );
}
