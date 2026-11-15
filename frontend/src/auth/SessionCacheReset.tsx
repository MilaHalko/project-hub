import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useToken } from "./tokenStore";

export function SessionCacheReset() {
  const client = useQueryClient();
  const token = useToken();
  const previous = useRef(token);

  useEffect(() => {
    if (previous.current && !token) client.clear();
    previous.current = token;
  }, [client, token]);

  return null;
}
