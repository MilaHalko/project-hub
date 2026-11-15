import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./errors";

function isClientError(error: unknown): boolean {
  return error instanceof ApiError && error.status >= 400 && error.status < 500;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) =>
          !isClientError(error) && failureCount < 1,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}
