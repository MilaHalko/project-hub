import type { Document } from "../api/documents";
import type { Project } from "../api/projects";

export const PROJECT_ID = "10000000-0000-4000-8000-000000000001";

export const project: Project = {
  id: PROJECT_ID,
  name: "Website redesign",
  description: "",
  owner: { id: "00000000-0000-4000-8000-000000000001", login: "mila" },
  my_role: "owner",
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-14T09:30:00Z",
};

export const brief: Document = {
  id: "20000000-0000-4000-8000-000000000001",
  project_id: PROJECT_ID,
  name: "Client brief.pdf",
  content_type: "application/pdf",
  size: 2_516_582,
  uploaded_by: { id: "00000000-0000-4000-8000-000000000001", login: "mila" },
  created_at: "2026-11-12T10:00:00Z",
  updated_at: "2026-11-14T09:00:00Z",
};

export const siteMap: Document = {
  id: "20000000-0000-4000-8000-000000000002",
  project_id: PROJECT_ID,
  name: "Site map.docx",
  content_type:
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  size: 839_680,
  uploaded_by: { id: "00000000-0000-4000-8000-000000000002", login: "sam" },
  created_at: "2026-11-12T08:00:00Z",
  updated_at: "2026-11-12T08:00:00Z",
};

export const infoRoute = `GET /api/project/${PROJECT_ID}/info`;
export const listRoute = `GET /api/project/${PROJECT_ID}/documents`;
export const uploadRoute = `POST /api/project/${PROJECT_ID}/documents`;

export function documentRoute(method: string, id: string): string {
  return `${method} /api/document/${id}`;
}
