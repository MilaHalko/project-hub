import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getMe, type User } from "../api/auth";
import type { ApiError } from "../api/errors";

export function useMe(): UseQueryResult<User, ApiError> {
  return useQuery<User, ApiError>({ queryKey: ["me"], queryFn: getMe });
}
