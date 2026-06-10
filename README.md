# droidland

A lightweight orchestration layer for Factory droids. droidland runs no droids itself: it calls
Factory's REST API to provision a managed (e2b) Droid Computer and create one Session per task on
it. Because those are real Factory sessions, they show up in
[app.factory.ai](https://app.factory.ai), and droidland deep-links to them.

droidland does three things and delegates everything else (code review, reading tickets, posting on
PRs) to Factory's native skills and Linear/GitHub integrations running inside each session:

1. **Author and catalog "experts"** - droids with personas plus declared skills/tools/integrations.
2. **Detect signals from GitHub and Linear by polling**, routing each match to one expert.
3. **Observe** running experts and session health, with deep links into app.factory.ai.

## Architecture

```
GitHub / Linear  --poll-->  Connectors  -->  Trigger Rules  -->  Factory API  -->  Droid Computer
                                                   |                                  (Sessions)
                                                   v                                      |
                                              SQLite + SSE  <----- Observability <---------+
                                                   |
                                              React UI (catalog, triggers, dashboard)
```

- **Experts** live as markdown in `.factory/droids/*.md` (YAML front-matter for model, autonomy,
  interaction mode, skills, integrations, worktree) plus a persona prompt body.
- **Triggers** map `(source, event_type, condition)` to an expert and a prompt template. On a match,
  droidland creates a tagged session and posts `persona + rendered task` as the first message.
  Activations are deduped by `(trigger, external_ref)`.
- **Compute** is one persistent shared Droid Computer per target repo, reused across runs.
- **Observability** polls Factory `List sessions` (filtered by the `droidland` tag) into a local
  cache and pushes updates to the UI over SSE.

## Prerequisites

- Docker and Docker Compose (recommended), or Python 3.12 and Node 20 for local dev.
- A Factory API key with the Sessions API enabled for your organization.
- Optional read-only tokens for detection: a GitHub token and/or a Linear API key.

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
| --- | --- |
| `DROIDLAND_FACTORY_API_KEY` | Factory API key (required). |
| `DROIDLAND_TARGET_REPO` | Repo for the shared Droid Computer (git URL or `owner/name`). |
| `DROIDLAND_GITHUB_TOKEN` | Read-only GitHub token for PR polling (optional). |
| `DROIDLAND_LINEAR_API_KEY` | Linear API key for issue polling (optional). |
| `DROIDLAND_POLL_INTERVAL_SECONDS` | Connector poll cadence (default 30). |
| `DROIDLAND_DEFAULT_MODEL` | Model used when an expert does not pin one. |

Secrets are read from the environment only and are never committed (`.env` is gitignored).

## Run with Docker

```bash
cp .env.example .env   # then edit values
docker compose up
```

- Backend (API + SSE): http://localhost:8000 (health at `/api/health`)
- Frontend (catalog, triggers, dashboard): http://localhost:5173

## Run locally (without Docker)

Backend:

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Tests and lint

```bash
cd backend
pip install -e ".[dev]"
pytest -q
ruff check .
```

## Prebuilt experts

Found in `.factory/droids/`: `code-reviewer`, `pr-risk-analyzer`, `ticket-triager`, `implementor`,
`test-writer`, `e2e-verifier`, `build-analyzer`. Each declares its settings in front-matter and ends
its work with a fenced JSON verdict block.

## API overview

`GET /api/health`, `GET /api/experts`, `GET /api/experts/{slug}`, `POST /api/experts/validate`,
`GET/POST/PUT /api/triggers`, `POST /api/triggers/{id}/test`, `GET /api/connectors`,
`POST /api/connectors/poll`, `GET /api/activations`, `GET /api/sessions`, `GET /api/computers`,
and `GET /api/stream` (SSE).

## Project layout

```
droidland/
  backend/app/        FastAPI app, Factory client, connectors, triggers, poller, observability
  backend/tests/      pytest suite (mocked Factory + connectors)
  frontend/           Vite + React + TypeScript UI
  .factory/droids/    prebuilt expert personas
  docker-compose.yml  backend + frontend services
```
