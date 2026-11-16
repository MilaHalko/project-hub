import type { APIRequestContext, Page } from "@playwright/test";
import { apiToken, createUser, signIn, type TestUser } from "./auth";
import { PDF, samplePdf, uploadViaApi } from "./documents";
import { expect, expectAccessible, test } from "./fixtures";
import { createProjectViaApi, inviteViaApi } from "./projects";

test.use({ expectedApiStatuses: [404] });

async function removedWhileOpen(
  page: Page,
  request: APIRequestContext,
): Promise<{ owner: TestUser; documentId: string }> {
  const owner = await createUser(request);
  const { id } = await createProjectViaApi(request, owner, {
    name: "Thesis materials",
  });
  const { id: documentId } = await uploadViaApi(request, owner, id, {
    name: "Owner notes.pdf",
    mimeType: PDF,
    buffer: samplePdf,
  });
  const participant = await signIn(page, request);
  await inviteViaApi(request, owner, id, participant.login);
  await page.goto(`/projects/${id}`);
  await expect(page.getByText("Owner notes.pdf")).toBeVisible();

  const participantToken = await apiToken(request, participant);
  const me = await request.get("/api/users/me", {
    headers: { Authorization: `Bearer ${participantToken}` },
  });
  const { id: participantId } = (await me.json()) as { id: string };
  const ownerToken = await apiToken(request, owner);
  const removed = await request.delete(
    `/api/project/${id}/members/${participantId}`,
    { headers: { Authorization: `Bearer ${ownerToken}` } },
  );
  expect(removed.status()).toBe(204);
  return { owner, documentId };
}

async function expectSentToProjects(page: Page) {
  await expect(
    page.getByText("You no longer have access to this project."),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 1, name: "Your projects" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "This document no longer exists. Someone may have deleted it.",
    ),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Thesis materials" }),
  ).toHaveCount(0);
}

test("tells a removed member they lost access when deleting a document", async ({
  page,
  request,
}) => {
  const { owner, documentId } = await removedWhileOpen(page, request);

  await page.getByRole("button", { name: "Delete Owner notes.pdf" }).click();
  await page
    .getByRole("alertdialog", { name: "Delete this document?" })
    .getByRole("button", { name: "Delete document" })
    .click();

  await expectSentToProjects(page);
  await expectAccessible(page);
  const token = await apiToken(request, owner);
  const kept = await request.get(`/api/document/${documentId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(kept.status()).toBe(200);
});

test("tells a removed member they lost access when downloading a document", async ({
  page,
  request,
}) => {
  await removedWhileOpen(page, request);

  await page.getByRole("button", { name: "Download Owner notes.pdf" }).click();

  await expectSentToProjects(page);
});
