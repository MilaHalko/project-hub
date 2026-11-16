import type { APIRequestContext } from "@playwright/test";

export const MAIL_URL = process.env.E2E_MAIL_URL ?? "http://127.0.0.1:8025";

const JOIN_LINK = /https?:\/\/\S+\/join\?token=[\w-]+/;

async function findMessageId(
  request: APIRequestContext,
  to: string,
): Promise<string> {
  const query = new URLSearchParams({ query: `to:"${to}"` });
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const response = await request.get(
      `${MAIL_URL}/api/v1/search?${query.toString()}`,
    );
    const { messages } = (await response.json()) as {
      messages: { ID: string }[];
    };
    const id = messages.at(0)?.ID;
    if (id !== undefined) return id;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`No mail to ${to} in Mailpit`);
}

export async function readJoinLink(
  request: APIRequestContext,
  to: string,
): Promise<string> {
  const id = await findMessageId(request, to);
  const response = await request.get(`${MAIL_URL}/api/v1/message/${id}`);
  const { Text } = (await response.json()) as { Text: string };
  const link = JOIN_LINK.exec(Text)?.[0];
  if (link === undefined) throw new Error(`No join link in the mail to ${to}`);
  return link;
}
