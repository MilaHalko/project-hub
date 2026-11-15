import { apiFetch } from "./client";

export type Document = {
  id: string;
  project_id: string;
  name: string;
  content_type: string;
  size: number;
  uploaded_by: { id: string; login: string } | null;
  created_at: string;
  updated_at: string;
};

export function listDocuments(projectId: string): Promise<Document[]> {
  return apiFetch<Document[]>(
    `/project/${encodeURIComponent(projectId)}/documents`,
  );
}
