import type { RouteObject } from "react-router";
import { AuthLayout } from "./auth/AuthLayout";
import { LoginPage } from "./auth/LoginPage";
import { RequireAuth } from "./auth/RequireAuth";
import { ProjectsPage } from "./projects/ProjectsPage";
import { NotFoundPage } from "./ui/NotFoundPage";

export const routes: RouteObject[] = [
  {
    element: <AuthLayout />,
    children: [{ path: "/login", element: <LoginPage /> }],
  },
  {
    path: "/",
    element: <RequireAuth />,
    children: [
      { index: true, element: <ProjectsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
