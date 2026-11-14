import { Navigate, useLocation } from "react-router";
import { Layout } from "../ui/Layout";
import { getEndReason, useToken } from "./tokenStore";

export function RequireAuth() {
  const token = useToken();
  const { pathname, search } = useLocation();
  if (token) return <Layout />;
  return (
    <Navigate
      to={`/login?next=${encodeURIComponent(pathname + search)}`}
      replace
      state={{ reason: getEndReason() }}
    />
  );
}
