import { Navigate, Outlet, useSearchParams } from "react-router";
import { saveJoinToken } from "./joinToken";

export function JoinLanding() {
  const [params] = useSearchParams();
  const token = params.get("token");
  if (token === null) return <Outlet />;
  saveJoinToken(token);
  return <Navigate to="/join" replace />;
}
