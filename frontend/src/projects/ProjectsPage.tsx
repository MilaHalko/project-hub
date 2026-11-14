import { Banner } from "../ui/Banner";
import styles from "./ProjectsPage.module.css";

export function ProjectsPage() {
  return (
    <>
      <Banner tag="PROJECT_HUB" title="Your projects">
        <p>Projects you own and projects you were invited to.</p>
      </Banner>
      <p className={styles.next}>Sign-in and the projects list come next.</p>
    </>
  );
}
