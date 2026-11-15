import { Link } from "react-router";
import { Banner } from "./Banner";
import { buttonClassName } from "./Button";

export function NotFoundPage() {
  return (
    <>
      <Banner tag="ERROR 404" title="Page not found">
        <p>
          This page does not exist. Check the address or go back to your
          projects.
        </p>
      </Banner>
      <Link to="/projects" className={buttonClassName()}>
        Go to projects
      </Link>
    </>
  );
}
