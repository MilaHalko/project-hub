import { readFileSync } from "node:fs";
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { apiToken, type TestUser } from "./auth";

export const PDF = "application/pdf";
export const DOCX =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export const samplePdf = readFileSync(
  new URL("files/sample.pdf", import.meta.url),
);
export const sampleDocx = readFileSync(
  new URL("files/sample.docx", import.meta.url),
);

export type UploadFile = { name: string; mimeType: string; buffer: Buffer };

export async function uploadViaApi(
  request: APIRequestContext,
  user: TestUser,
  projectId: string,
  file: UploadFile,
): Promise<{ id: string }> {
  const token = await apiToken(request, user);
  const response = await request.post(`/api/project/${projectId}/documents`, {
    multipart: { files: file },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status() !== 201) {
    throw new Error(
      `POST /api/project/${projectId}/documents answered ${String(response.status())}`,
    );
  }
  const [{ id }] = (await response.json()) as [{ id: string }];
  return { id };
}

export async function animationsDone(page: Page): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate<boolean>(
        "document.getAnimations().every((animation) => animation.playState !== 'running')",
      ),
    )
    .toBe(true);
}
