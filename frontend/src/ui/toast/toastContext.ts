import { createContext } from "react";

export interface ToastApi {
  success(text: string): void;
  error(text: string): void;
}

export const ToastContext = createContext<ToastApi | null>(null);
