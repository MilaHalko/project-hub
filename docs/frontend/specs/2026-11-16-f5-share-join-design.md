# F5 — Share and join

Date: 2026-11-16
Status: approved by the user (2026-11-16): join only after a click on "Join project" (option A)
Parent design: [`../2026-11-14-frontend-design.md`](../2026-11-14-frontend-design.md)
Roadmap row: [`../roadmap.md`](../roadmap.md) (F5)
Mockup: [`../mockups/f5-share-join.html`](../mockups/f5-share-join.html) (open in a browser)
API: epic 10,
[`docs/superpowers/specs/2026-11-16-share-join-design.md`](../../superpowers/specs/2026-11-16-share-join-design.md)

## Intent

The owner brings someone into a project without knowing their login: types an
email address, and Project Hub mails a link. Whoever opens the link and signs
in becomes a participant. This is the spec's optional share endpoint, shown in
the defense demo: Mila shares her project, the mail arrives in Mailpit, Anna
opens the link, signs in and sees the project; the same link fails the second
time. The API is merged (epic 10, PR #36); this epic only calls it.

## Goals

- A "Send a link by email" form on the project page, owner only.
- A `/join` page in the web app that the mail link ends up on (the API answers
  a browser with `303` to it), signs a signed-out user in first, joins with the
  Bearer header and shows the result.
- The join token never stays in the address bar, in the web server's logs or in
  a URL the app builds.
- `APP_WEB_URL` set wherever `frontend/compose.yml` runs the API.
- End-to-end tests for both flows that read the real mail from Mailpit.
- Every state at 1280 px and 375 px.

## Non-goals

- A list of pending links and revoking one (postponed in epic 10).
- Copying the link from the app: the API never returns the token.
- Binding a link to a user's email (users have no email).
- Anything in the backend.

## Anti-goals

Those of the parent design and F3, and in particular:

- a participant who sees the share form;
- a link that joins on its own when the page opens, so a shared computer joins
  the wrong account or a reload uses the link up;
- the token left in the address bar, the browser history, the login page URL
  or an nginx log line;
- "Link sent" when nothing was sent, or an error that does not say what to do;
- an expired, used and unknown link told apart (the API makes them identical).

## Constraints

- API facts (epic 10):
  - `GET /project/<id>/share?with=<email>` (Bearer, no body) → 200
    `{email (lower case), expires_at}`. Errors in this order: 401; 503 `Email
    sharing is not configured`; 422 (bad address, spaces around it, over 254
    characters); 404 `Project not found`; 403 `Only the project owner can
    share the project`; 429 `Too many pending share links for this project`
    (10 pending per project; sharing to an address that already has a link
    replaces it and does not count); 503 `Email could not be sent` (nothing
    stored). A repeat share to the same address makes the old link stop
    working.
  - The mail holds `<APP_PUBLIC_URL>/join?token=…` (the API). A browser
    without `Authorization` and with `Accept: text/html` gets `303` to
    `<APP_WEB_URL>/join?token=<url-encoded>`.
  - `GET /join?token=…` with Bearer → 200 `{login, already_member, project}`,
    where `project` is the `/project/<id>/info` object with `my_role`. 404
    `Invite link is invalid or expired` for unknown, expired, used, replaced
    links and deleted projects alike; 422 for an empty or over-128-character
    token; 401 on a bad JWT. Someone who already has access gets 200 with
    `already_member: true`, and the link is **not** used up.
  - A second `GET /join` after a successful one answers 404 (the link is gone
    before the "already a member" check), so the page must call it once.
- The JWT lives in `sessionStorage` (F1); `apiFetch` adds the Bearer header and
  ends the session on 401.
- `RequireAuth` sends a signed-out user to `/login?next=<path and query>`; log
  in and register keep `next`.
- Frontend rules from `CLAUDE.md`: only `frontend/`, `docs/frontend/`, the
  frontend workflow and the roadmap's "Frontend requests" section change.
  `frontend/compose.yml` may add environment to the root compose's `api`
  service; the root `docker-compose.yml` stays as it is.

## Approaches

### When the join happens

| Option | Trade-off | Decision |
|---|---|---|
| **The page shows "You are logged in as @anna" and a "Join project" button** | One more click. The person sees which account will join before the single-use link is spent; a reload or a second render never spends it; "Log out" next to it lets someone else on the same computer join instead | **Chosen** (user, 2026-11-16) |
| Join as soon as the page opens | One click less in the demo; the wrong account joins on a shared computer, and the page needs a guard so React does not call it twice (the second call answers 404) | Rejected |

### Where the token waits while the user signs in

| Option | Trade-off | Decision |
|---|---|---|
| **`sessionStorage`, key `project-hub.join-token`, removed once the join answers 200 or 404/422** | Survives the login redirect, a reload of the login page and "Create account"; the tab's storage is where the JWT already lives; never in a URL after landing | **Chosen** (user, 2026-11-16) |
| In memory only | Gone on a reload of the login page or if the user registers in a new render; the link would then look broken | Rejected |
| In the `next` URL (`/login?next=/join?token=…`) | The token sits in the address bar and history of the login page and register page | Rejected (anti-goal) |

### Where the share form lives

| Option | Trade-off | Decision |
|---|---|---|
| **In the members panel, under "Invite by login", with its own label** | Both ways of adding people in one place; the panel already is owner-aware | **Chosen** (user, 2026-11-16) |
| Own "Share" dialog from the banner | One more click and a second place for "add people" | Rejected |

## Additions beyond the roadmap row

Planner's calls, shown to the user with this design (2026-11-16):

| Addition | Why | Cost |
|---|---|---|
| Log in page line "Log in or create an account to join the project." when `next` is `/join` | The person came from an email and should know why they see a log in form | one line and one test |
| nginx error log quiet for `/api/join` (`error_log … crit` in its own location) | When the API is down, nginx's error line repeats the request line with the token | one location block, checked by a command |

## Design

### Share form (mockup 1, 2, 5)

- Owner only, in the members panel under the invite form, separated by a line:
  field labelled "Send a link by email" (`type="email"`, `autocomplete="off"`,
  `inputmode="email"`), hint under it "The link works once, for 7 days.",
  button "Send link" (secondary: "Invite" stays the panel's one primary
  button; full width).
- The address is trimmed before checks and sending. Checks on submit, then
  while typing: empty "Enter an email address."; no `name@domain` shape
  (`^[^\s@]+@[^\s@]+$`) "Enter an address like name@example.com."; over 254
  characters "Use 254 characters or fewer." Nothing is sent while a check
  fails. The server does the full check.
- While the request runs the button shows the spinner and ignores clicks.
- Success: the field clears and keeps the focus; toast "Link sent to
  <email>. It works until <Nov 23, 2026, 14:05>." (`formatDateTime`, local
  time). The members list does not change: nobody joined yet.
- Errors under the field (`aria-describedby`, `aria-invalid`), the typed
  address stays:
  - 422 → "Check the email address and try again.";
  - 429 → "This project already has 10 unused links. Wait until one is
    used or expires, or invite by login.";
  - 503 `Email sharing is not configured` → "Email isn't set up on this
    server. Invite people by login instead.";
  - 503 `Email could not be sent` → "Couldn't send the email. Try again
    later.";
  - 403 → "Only the owner can share the project.";
  - network or anything else → "Couldn't send the link. Try again.";
  - 404 `Project not found` → as F3's invite: go to `/projects`, toast "This
    project no longer exists."

### Landing on `/join?token=…`

- The route `/join` sits outside the guard. When the address has `token`, the
  page saves it to `sessionStorage` and replaces the address with `/join`
  (`replace`, so Back never shows the token). Then the normal guard runs: a
  signed-out user goes to `/login?next=%2Fjoin`. Log in, or "Create account"
  and log in, bring them back to `/join`.
- A new `token` in the address replaces a saved one (the newest link wins).

### Join page (mockup 3, 4, 5), signed in

Inside the normal layout (sidebar), a banner and one action row.

- **Ready** (a saved token): tag `INVITE`, title "Join a project", text "You
  are logged in as @anna. Join with this account, or log out to use another
  one." Buttons: "Join project" (primary) and "Log out" (secondary,
  logs out; the token stays saved, so the next person who logs in lands here
  again).
- **Joining**: "Join project" shows the spinner and ignores clicks.
- **Joined** (`already_member: false`): role badge on white above the tag
  (as on the project page), tag `JOINED`, title = project name, text = the
  description if any; under it "You joined as @anna. You are a
  participant now." and the "Open project" link (primary button look). The
  saved token is removed; the project goes into the query cache, the projects
  lists refresh. Focus moves to the heading.
- **Already a member** (`already_member: true`): role badge, tag `ALREADY A
  MEMBER`, title = project name; "You already have access as @mila. The link was not
  used, so it still works for the person it was sent to." and "Open project".
  The saved token is removed from this tab.
- **Link doesn't work** (404 or 422): tag `LINK NOT VALID`, title "This link
  doesn't work", text "It may have expired, been used already, or been
  replaced by a newer link. Ask the project owner to send a new one." and "Go
  to your projects". The saved token is removed.
- **No link** (`/join` without a saved token, for example after a reload of a
  finished join): tag `INVITE`, title "No invite link", "Open the link from
  your email again." and "Go to your projects".
- **Failed** (network, 5xx): the ready state stays, with "Couldn't join the
  project. Try again." above the buttons (`role="alert"`); the token stays.
- **401**: the session ends as everywhere (F1): log in again, then back to
  `/join` with the token still saved.

### Log in page

- When `next` is `/join`, the line "Log in or create an account to join the
  project." shows above the form (unless a session-expired or logged-out
  notice is shown).

### nginx and compose

- `frontend/nginx/default.conf` logs requests with their path only: a
  `log_format` that writes `$request_method <path without query>
  $server_protocol` and the referrer without its query (`map` on
  `$request_uri` and `$http_referer`). No query string reaches the access log,
  so neither `/join?token=…` (the page) nor `/api/join?token=…` (the API call)
  does.
- `location = /api/join` repeats the API proxy with `error_log … crit`, so an
  upstream failure does not write the request line either.
- `frontend/compose.yml` sets `APP_WEB_URL` on the `api` service to
  `http://127.0.0.1:${WEB_PORT:-8080}` (overridable with `APP_WEB_URL`), the
  same origin the README and the end-to-end tests open, because the JWT in
  `sessionStorage` belongs to one origin.

### Tests

- Component tests (Vitest, mocked API): every share state; the join page's
  landing (token saved, address cleaned), each state, one call per click; the
  log in line.
- End-to-end (real stack, axe on every page):
  - share: owner sends a link, the toast shows, the mail is in Mailpit
    (`E2E_MAIL_URL`, default `http://127.0.0.1:8025`) and holds the API join
    link; an address the server rejects shows the message under the field;
  - join, signed out: the test reads the mail, requests its link like a
    browser (`Accept: text/html`, no redirect follow) and checks the `303`
    points at the web app's `/join`; the browser opens that, lands on log in
    with no token in the address, logs in as another user, joins, opens the
    project as a participant; the same link then shows "This link doesn't
    work";
  - join, already a member: the owner opens their own link and sees "already
    have access"; then another user still joins with it.
- nginx log: a CI step after the browser tests checks the `web` container's
  log has `GET /api/join` lines and no `token=`; run once locally too, and the
  `error_log` line once with the API stopped.

## Left to the builder

- Component and file names, CSS, how the landing and the guard are split in
  `routes.tsx`.
- The exact Mailpit API calls (search by recipient, read the text).
