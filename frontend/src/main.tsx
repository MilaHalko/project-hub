import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/space-mono/latin-400.css";
import "@fontsource/space-mono/latin-700.css";
import "./styles/tokens.css";
import "./styles/global.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { AppProviders } from "./AppProviders";
import { routes } from "./routes";

const router = createBrowserRouter(routes);
const root = document.getElementById("root");
if (!root) throw new Error("The page has no #root element");

createRoot(root).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
);
