# Project Hub web app

The React app for Project Hub. It is an addition beyond the spec and sits beside
the API: the backend does not depend on it. Its plan and decisions are in
[`docs/frontend/`](../docs/frontend/README.md).

## Requirements

Node 26.13.1 (pinned in `.nvmrc`) and npm. All commands run in `frontend/`.

## Run

```bash
npm ci
npm run dev        # http://localhost:5173/, /api/… proxied to the API on localhost:8000
```

The app calls the API under `/api/` (for example `/api/login` for `POST /login`); the dev
server strips the prefix, so start the API as described in the root
[`README.md`](../README.md).

## Checks

```bash
npm run lint       # ESLint and Prettier
npm run typecheck
npm test           # component tests (Vitest)
npm run build      # writes dist/
npm audit --audit-level=high
```

`npm run format` fixes formatting.

## CI

`.github/workflows/frontend.yml` runs on pull requests and pushes to `main` that touch
`frontend/` or the workflow itself.

- Job `frontend`: `npm ci`, then the checks above.
