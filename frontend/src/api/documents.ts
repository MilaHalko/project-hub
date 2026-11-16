import { apiFetch, apiFetchBlob } from "./client";

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

export async function uploadDocument(
  projectId: string,
  file: File,
): Promise<Document> {
  const form = new FormData();
  form.append("files", file);
  const [document] = await apiFetch<[Document]>(
    `/project/${encodeURIComponent(projectId)}/documents`,
    { method: "POST", body: form },
  );
  return document;
}

export function downloadDocument(id: string): Promise<Blob> {
  return apiFetchBlob(`/document/${encodeURIComponent(id)}`);
}

export function replaceDocument(id: string, file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<Document>(`/document/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: form,
  });
}
