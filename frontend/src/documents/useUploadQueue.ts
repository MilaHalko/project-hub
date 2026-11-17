import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { uploadDocument } from "../api/documents";
import { ApiError } from "../api/errors";
import { useToast } from "../ui/toast/useToast";
import { documentsChanged, reloadSpace } from "./documentsCache";
import { checkFile, uploadErrorMessage } from "./fileRules";

export type UploadItem = {
  key: string;
  file: File;
  state: "waiting" | "uploading" | "failed";
  error?: string;
};

export function useUploadQueue(projectId: string) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [items, setItems] = useState<UploadItem[]>([]);
  const [announcement, setAnnouncement] = useState("");
  const waiting = useRef<UploadItem[]>([]);
  const running = useRef(false);
  const nextKey = useRef(0);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  function change(key: string, patch: Partial<UploadItem> | null) {
    setItems((current) =>
      patch === null
        ? current.filter((item) => item.key !== key)
        : current.map((item) =>
            item.key === key ? { ...item, ...patch } : item,
          ),
    );
  }

  function fail(key: string, error: string) {
    if (!mounted.current) {
      toast.error(error);
      return;
    }
    change(key, { state: "failed", error });
    setAnnouncement(error);
  }

  async function run() {
    if (running.current) return;
    running.current = true;
    let saved = 0;
    for (
      let item = waiting.current.shift();
      item;
      item = waiting.current.shift()
    ) {
      change(item.key, { state: "uploading" });
      try {
        const document = await uploadDocument(projectId, item.file);
        saved += 1;
        change(item.key, null);
        documentsChanged(queryClient, projectId, (documents) => [
          document,
          ...documents,
        ]);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          const dropped = new Set(waiting.current.map(({ key }) => key));
          dropped.add(item.key);
          waiting.current = [];
          setItems((current) => current.filter(({ key }) => !dropped.has(key)));
          break;
        }
        if (error instanceof ApiError && error.status === 413) {
          reloadSpace(queryClient, projectId);
        }
        fail(item.key, uploadErrorMessage(error, item.file.name));
      }
    }
    running.current = false;
    if (saved === 1) toast.success("File uploaded");
    if (saved > 1) toast.success(`${String(saved)} files uploaded`);
  }

  function add(files: File[]) {
    const added: UploadItem[] = files.map((file) => {
      nextKey.current += 1;
      const key = String(nextKey.current);
      const error = checkFile(file);
      return error === null
        ? { key, file, state: "waiting" }
        : { key, file, state: "failed", error };
    });
    if (added.length === 0) return;
    setItems((current) => [...current, ...added]);
    const refused = added.filter(({ error }) => error !== undefined);
    if (refused.length > 0)
      setAnnouncement(refused.map(({ error }) => error).join(" "));
    waiting.current.push(...added.filter(({ state }) => state === "waiting"));
    void run();
  }

  function dismiss(key: string) {
    change(key, null);
  }

  return { items, announcement, add, dismiss };
}
