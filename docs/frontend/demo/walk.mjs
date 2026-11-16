import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(
  path.join(here, "../../../frontend/package.json"),
);
const { chromium } = require("@playwright/test");

const WEB = process.env.DEMO_WEB ?? "http://127.0.0.1:8100";
const API = process.env.DEMO_API ?? "http://127.0.0.1:8020";
const ANNA = { login: "anna", password: "anna1234" };
const BORIS = { login: "boris", password: "boris1234" };
const NEW_PASSWORD = "anna-new-5678";
const DEMO_PROJECT = "Демо для ментора";

const bugs = [];
let step = 0;

async function shot(page, name) {
  step += 1;
  const file = `${String(step).padStart(2, "0")}-${name}.jpeg`;
  await page.waitForTimeout(400);
  await page.screenshot({
    path: path.join(here, file),
    type: "jpeg",
    quality: 70,
  });
  console.log("shot", file, page.url());
}

async function api(method, url, token, body) {
  const response = await fetch(API + url, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  return { status: response.status, json: text ? JSON.parse(text) : null };
}

async function token(user) {
  const { status, json } = await api("POST", "/login", null, user);
  if (status !== 200) throw new Error(`login ${user.login}: ${status}`);
  return json.access_token;
}

async function logIn(page, user) {
  await page.goto(`${WEB}/login`);
  await page.getByRole("textbox", { name: "Login" }).fill(user.login);
  await page.getByRole("textbox", { name: "Password" }).fill(user.password);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL("**/projects");
  await page.getByRole("table").waitFor();
}

async function openProject(page, name) {
  await page.getByRole("link", { name: "Projects" }).first().click();
  await page.getByRole("link", { name }).click();
  await page.getByRole("heading", { name, level: 1 }).waitFor();
}

async function check(label, fn) {
  try {
    await fn();
  } catch (error) {
    bugs.push(`${label}: ${error.message.split("\n")[0]}`);
    console.log("PROBLEM", label, error.message.split("\n")[0]);
  }
}

async function walk(page) {
  await page.goto(`${WEB}/register`);
  await page.getByRole("textbox", { name: "Login" }).fill("gleb");
  await page
    .getByRole("textbox", { name: "Password", exact: true })
    .fill("gleb12345");
  await page
    .getByRole("textbox", { name: "Repeat password" })
    .fill("gleb54321");
  await page
    .getByRole("button", { name: /create account|sign up|register/i })
    .click();
  await shot(page, "register-mismatch");

  await page.goto(`${WEB}/login`);
  await page.getByRole("textbox", { name: "Login" }).fill("anna");
  await page.getByRole("textbox", { name: "Password" }).fill("wrong-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await page.getByRole("alert").filter({ hasText: /./ }).first().waitFor();
  await shot(page, "login-wrong-password");

  await logIn(page, ANNA);
  await shot(page, "projects-all");
  await page.getByRole("link", { name: "Owned" }).click();
  await page.waitForURL("**role=owner");
  await shot(page, "projects-owned");
  await page.getByRole("link", { name: "Shared with me" }).click();
  await page.waitForURL("**role=participant");
  await shot(page, "projects-shared");

  await page.getByRole("button", { name: "New project" }).first().click();
  const create = page.locator("dialog[open]");
  await create.getByRole("textbox", { name: "Name" }).fill(DEMO_PROJECT);
  await create
    .getByRole("textbox", { name: "Description (optional)" })
    .fill("Проект, созданный прямо на защите.");
  await shot(page, "project-create-dialog");
  await create.getByRole("button", { name: "Create project" }).click();
  await page.getByRole("heading", { name: DEMO_PROJECT, level: 1 }).waitFor();
  await shot(page, "project-page-new");

  await page.getByRole("button", { name: "Edit" }).click();
  const edit = page.locator("dialog[open]");
  await edit
    .getByRole("textbox", { name: "Description (optional)" })
    .fill("Описание поменяли на защите.");
  await edit.getByRole("button", { name: "Save changes" }).click();
  await page.getByText("Описание поменяли на защите.").first().waitFor();
  await shot(page, "project-edited");

  const invite = page.getByRole("textbox", { name: "Invite by login" });
  await invite.fill("nobody");
  await page.getByRole("button", { name: "Invite", exact: true }).click();
  await page.getByText("No user with that login").waitFor();
  await shot(page, "invite-unknown-login");
  await invite.fill("vera");
  await page.getByRole("button", { name: "Invite", exact: true }).click();
  await page.getByRole("button", { name: "Remove vera" }).waitFor();
  await shot(page, "invite-vera");

  await page.getByRole("button", { name: "Remove vera" }).click();
  await shot(page, "remove-vera-dialog");
  await page
    .locator("dialog[open]")
    .getByRole("button", { name: "Remove" })
    .click();
  await page
    .getByRole("button", { name: "Remove vera" })
    .waitFor({ state: "detached" });
  await shot(page, "vera-removed");

  await page.getByRole("button", { name: "Delete project" }).click();
  const del = page.locator("dialog[open]");
  await del
    .getByRole("textbox", { name: "Type the project name to confirm" })
    .fill(DEMO_PROJECT);
  await shot(page, "delete-project-dialog");
  await del.getByRole("button", { name: /delete/i }).click();
  await page.waitForURL("**/projects");
  await shot(page, "project-deleted");

  await openProject(page, "Дипломный проект");
  await shot(page, "owner-project-members");

  await openProject(page, "Поездка в Карпаты");
  await shot(page, "participant-project");
  await page.getByRole("button", { name: "Leave project" }).click();
  await shot(page, "leave-dialog");
  await page
    .locator("dialog[open]")
    .getByRole("button", { name: /leave/i })
    .click();
  await page.waitForURL("**/projects");
  await shot(page, "after-leave");

  await page.getByRole("link", { name: "Profile" }).click();
  await page.waitForURL("**/profile");
  await page.getByLabel("Current password").waitFor();
  await page.getByLabel("Current password").fill("wrong-password");
  await page.getByLabel("New password", { exact: true }).fill(NEW_PASSWORD);
  await page.getByLabel("Repeat new password").fill(NEW_PASSWORD);
  await page.getByRole("button", { name: "Change password" }).click();
  await page.getByText("Current password is wrong").waitFor();
  await shot(page, "password-wrong-current");
  await page.getByLabel("Current password").fill(ANNA.password);
  await page.getByLabel("New password", { exact: true }).fill(NEW_PASSWORD);
  await page.getByLabel("Repeat new password").fill(NEW_PASSWORD);
  await page.getByRole("button", { name: "Change password" }).click();
  await page.getByText("Password changed").first().waitFor();
  await shot(page, "password-changed");

  await page.getByRole("button", { name: "Log out" }).click();
  await page.waitForURL("**/login**");
  await shot(page, "logged-out");

  await logIn(page, { login: ANNA.login, password: NEW_PASSWORD });
  await page.evaluate(() =>
    sessionStorage.setItem("project-hub.token", "expired.token.value"),
  );
  await page.getByRole("link", { name: "Profile" }).click();
  await page.waitForURL("**/login**");
  await shot(page, "session-expired");
}

async function swagger(page) {
  await page.goto(`${API}/docs`);
  await page.locator(".opblock").first().waitFor();
  await shot(page, "swagger-overview");

  const login = page
    .locator(".opblock", { has: page.locator('[data-path="/login"]') })
    .first();
  await login.locator(".opblock-summary").click();
  await login.getByRole("button", { name: "Try it out" }).click();
  await login
    .locator("textarea.body-param__text")
    .fill(
      JSON.stringify({ login: ANNA.login, password: ANNA.password }, null, 2),
    );
  await login.getByRole("button", { name: "Execute" }).click();
  await login
    .locator(".live-responses-table .response-col_status")
    .first()
    .waitFor();
  await login.locator(".responses-wrapper").scrollIntoViewIfNeeded();
  await shot(page, "swagger-login-token");

  const jwt = await token(ANNA);
  await page.locator("button.authorize").first().click();
  await page.locator(".auth-container input").first().fill(jwt);
  await shot(page, "swagger-authorize");
  await page.locator(".auth-btn-wrapper button.authorize").click();
  await page.locator(".auth-btn-wrapper button", { hasText: "Close" }).click();

  const me = page
    .locator(".opblock", { has: page.locator('[data-path="/users/me"]') })
    .first();
  await me.locator(".opblock-summary").click();
  await me.getByRole("button", { name: "Try it out" }).click();
  await me.getByRole("button", { name: "Execute" }).click();
  await me
    .locator(".live-responses-table .response-col_status")
    .first()
    .waitFor();
  await me.locator(".responses-wrapper").scrollIntoViewIfNeeded();
  await shot(page, "swagger-users-me-200");
}

async function restore() {
  const changed = await api("POST", "/login", null, {
    login: ANNA.login,
    password: NEW_PASSWORD,
  });
  if (changed.status === 200) {
    const reset = await api(
      "PUT",
      "/users/me/password",
      changed.json.access_token,
      {
        current_password: NEW_PASSWORD,
        new_password: ANNA.password,
        repeat_new_password: ANNA.password,
      },
    );
    console.log("restore anna password", reset.status);
  }
  const boris = await token(BORIS);
  const { json: projects } = await api(
    "GET",
    "/projects?role=owner&limit=100",
    boris,
  );
  const trip = projects.find((p) => p.name === "Поездка в Карпаты");
  const { json: members } = await api(
    "GET",
    `/project/${trip.id}/members`,
    boris,
  );
  if (!members.some((m) => m.login === "anna")) {
    const invited = await api(
      "POST",
      `/project/${trip.id}/invite?user=anna`,
      boris,
    );
    console.log("restore anna in trip", invited.status);
  }
  const anna = await token(ANNA);
  const { json: own } = await api(
    "GET",
    "/projects?role=owner&limit=100",
    anna,
  );
  for (const p of own.filter((p) => p.name === DEMO_PROJECT)) {
    console.log(
      "restore delete leftover",
      (await api("DELETE", `/project/${p.id}`, anna)).status,
    );
  }
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const consoleErrors = [];
page.on(
  "console",
  (m) =>
    m.type() === "error" && consoleErrors.push(`${page.url()} ${m.text()}`),
);
await check("walk", () => walk(page));
await restore();
const docs = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await check("swagger", () => swagger(docs));
await browser.close();
console.log("console errors:", consoleErrors.length ? consoleErrors : "none");
console.log("problems:", bugs.length ? bugs : "none");
