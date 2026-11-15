import { QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { SessionCacheReset } from "./auth/SessionCacheReset";
import { createQueryClient } from "./api/queryClient";
import { ToastProvider } from "./ui/toast/ToastProvider";

export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(createQueryClient);
  return (
    <QueryClientProvider client={client}>
      <SessionCacheReset />
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}
