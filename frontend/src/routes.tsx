import type { RouteObject } from "react-router";
import { AuthLayout } from "./auth/AuthLayout";
import { LoginPage } from "./auth/LoginPage";
import { RegisterPage } from "./auth/RegisterPage";
import { RequireAuth } from "./auth/RequireAuth";
import { ProfilePage } from "./profile/ProfilePage";
import { ProjectsPage } from "./projects/ProjectsPage";
import { NotFoundPage } from "./ui/NotFoundPage";

export const routes: RouteObject[] = [
  {
    element: <AuthLayout />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },
  {
    path: "/",
    element: <RequireAuth />,
    children: [
      { index: true, element: <ProjectsPage /> },
      { path: "profile", element: <ProfilePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
