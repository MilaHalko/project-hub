import type { RouteObject } from "react-router";
import { ProjectsPage } from "./projects/ProjectsPage";
import { Layout } from "./ui/Layout";
import { NotFoundPage } from "./ui/NotFoundPage";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <ProjectsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
