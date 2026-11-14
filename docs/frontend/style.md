# Frontend style

Approved by the user on 2026-11-14. Reference mockup:
[`mockups/look.html`](mockups/look.html) (projects list, project page, log in).
Open it in a browser; it is a picture of the look, not production code.

## Idea

Strict black-and-white working UI with two accent colours, and a soft
holographic gradient used only as a background for big titles. The working
parts (tables, forms, lists) stay calm; the gradient makes headers memorable.

Inspiration the user brought: a monochrome inventory dashboard (layout,
tables, black buttons), a holographic agency site (gradient, monospace
headings), a warm project-management board (soft, rounded).

## Tokens

These become CSS variables in `frontend/src/styles/tokens.css`. Names are the
builder's call; values are the agreed look.

| Token | Value | Use |
|---|---|---|
| ink | `#111111` | text, primary buttons, holographic borders |
| muted | `#6b6b73` | secondary text |
| line | `#e7e7ea` | borders, table lines |
| soft | `#fafafa` | sidebar, table header |
| surface | `#ffffff` | page and cards |
| violet | `#5b4ce0` | links, active nav, progress |
| violet-bg / violet-ink | `#efedff` / `#3a2fa8` | owner badge, active nav item |
| mint | `#0f9d76` | success |
| mint-bg / mint-ink | `#e3f6ef` / `#0b6b51` | participant badge, success toast |
| warn | `#e0821b` | used space above 80 % |
| danger | `#b42318` | destructive buttons and errors |
| holo | `linear-gradient(115deg, #ffc9a8 0%, #ffe9a8 20%, #c4f0dc 40%, #bfe2ff 60%, #ddcbff 80%, #ffc6d8 100%)` | title banners, login panel, logo mark |
| radius | 8 px controls, 10 px tables and panels, 14 px banners | |

Text on the holographic gradient is always `ink` (dark): the gradient is kept
pastel so dark text passes WCAG AA contrast. Never put light text on it.

## Type

- **Inter** for everything: body 14 px, table 13 px, small labels 12 px; weights
  400, 500, 600.
- **Space Mono** only for big titles on the holographic banners (28–40 px,
  bold, slight negative letter spacing) and the small all-caps tag above them.
- Both self-hosted (`@fontsource/inter`, `@fontsource/space-mono`).

## Components

- **Layout**: left sidebar 220 px (logo, Projects, Profile, Log out) with the
  `soft` background; content on white. At phone width the sidebar becomes a
  top bar with a menu button.
- **Banner**: holographic background, radius 14 px, tag + Space Mono title +
  one line of text. Used on: projects list (title "Your projects"), project page
  (project name, role badge, Edit / Delete buttons), log in and register (left
  panel).
- **Buttons**: primary black with white text; secondary white with a `line`
  border; destructive secondary with `danger` text. One primary button per view.
- **Badges**: owner = violet-bg / violet-ink, participant = mint-bg /
  mint-ink; 11 px, weight 600, radius 6 px.
- **Tables and lists**: bordered container, `soft` header row, thin row lines.
- **Upload zone**: dashed violet border on a very light violet background.
- **File type tiles**: PDF on light red, DOCX on light blue, 34 px squares.
- **Used-space bar**: 6 px, violet; `warn` above 80 %. Rendered only when the
  API returns the numbers.
- **Avatars**: preset geometric SVG icons in the holographic colours, round,
  26–28 px in lists.
- **Global loader**: 2–3 px violet bar at the very top of the window.
- **Toasts**: bottom right (bottom centre on phones), white with a `line`
  border, mint icon for success, danger icon for errors.

## Words

- English only, sentence case ("Create project", not "Create Project").
- Buttons start with a verb, 1–3 words.
- Errors say what happened and what to do: "That login is taken. Try another."
- Empty states invite: "Create your first project".
- No "please", no "successfully", no exclamation marks.
- Never the course provider's company name (AWS sandbox rule).
