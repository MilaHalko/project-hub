import { useMe } from "../auth/useMe";
import { Banner } from "../ui/Banner";
import styles from "./ProjectsPage.module.css";

export function ProjectsPage() {
  const { data: user } = useMe();
  return (
    <>
      <Banner
        tag={user ? `HI, ${user.login.toUpperCase()}` : "PROJECT_HUB"}
        title="Your projects"
      >
        <p>Projects you own and projects you were invited to.</p>
      </Banner>
      <p className={styles.next}>Sign-in and the projects list come next.</p>
    </>
  );
}
