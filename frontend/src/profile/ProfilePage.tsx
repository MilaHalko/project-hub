import { useMe } from "../auth/useMe";
import { messageFor } from "../api/errors";
import { Avatar } from "../ui/avatar/Avatar";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import styles from "./ProfilePage.module.css";

const memberSince = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

export function ProfilePage() {
  const { data: user, error, refetch } = useMe();

  if (user) {
    return (
      <Banner
        tag="PROFILE"
        title={user.login}
        aside={<Avatar userId={user.id} size={56} />}
      >
        <p>Member since {memberSince.format(new Date(user.created_at))}</p>
      </Banner>
    );
  }

  if (error) {
    return (
      <>
        <Banner tag="PROFILE" title="Profile" />
        <div className={styles.error} role="alert">
          <p>{messageFor(error)}</p>
          <Button
            variant="secondary"
            onClick={() => {
              void refetch();
            }}
          >
            Try again
          </Button>
        </div>
      </>
    );
  }

  return (
    <div className={styles.skeleton} aria-hidden="true">
      <span className={styles.skeletonAvatar} />
      <span className={styles.skeletonLines}>
        <span />
        <span />
      </span>
    </div>
  );
}
