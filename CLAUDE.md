# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Summary

DeerFlow is an open-source **super agent harness** — a LangGraph-based AI agent system that orchestrates sub-agents, memory, sandboxes, and extensible skills. It's a full-stack application:

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend | Next.js 16, React 19, TypeScript 5.8, Tailwind CSS 4, pnpm | 3000 |
| Gateway API | Python 3.12, FastAPI + embedded LangGraph runtime | 8001 |
| Reverse Proxy | Nginx (unified entry point) | 2026 |
| Provisioner | Optional, for Kubernetes sandbox mode | 8002 |

Python dependencies are managed with `uv` (workspace monorepo), frontend with `pnpm`. The backend is split into a reusable **harness** package (`deerflow-harness`, import prefix `deerflow.*`) and the **app** layer (`app.*`) with a strict one-way dependency: `app` imports `deerflow`, never the reverse.

## Common Commands

All commands run from the **repository root** unless noted.

### Setup & Diagnosis

```bash
make check            # Verify required tools (node, pnpm, uv, nginx)
make install          # Install all dependencies (backend uv sync + frontend pnpm install + pre-commit hooks)
make config           # First-time: generate config.yaml from config.example.yaml (aborts if config exists)
make config-upgrade   # Merge new fields from config.example.yaml into existing config.yaml
make setup-sandbox    # Pre-pull the sandbox Docker image (optional, recommended)
```

### Development

```bash
make dev              # Start all services with hot-reload → http://localhost:2026
make dev-daemon       # Same as dev but in background
make stop             # Stop all services
```

### Docker

```bash
make docker-init      # Pull sandbox image and prepare Docker dev env
make docker-start     # Start Docker dev services → http://localhost:2026
make docker-stop      # Stop Docker dev services
make up               # Build and start production Docker stack
make down             # Stop production Docker stack
```

### Backend (from `backend/`)

```bash
make lint             # Ruff check + format check
make format           # Ruff auto-fix + format
make test             # Run all tests (PYTHONPATH=. uv run pytest tests/ -v)
make test-blocking-io # Strict blocking-IO gate (tests/blocking_io/)
make dev              # Gateway API only with reload (port 8001)
make gateway          # Gateway API without reload
```

Run a single test file:
```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_<feature>.py -v
```

### Frontend (from `frontend/`)

```bash
pnpm dev              # Dev server with Turbopack → http://localhost:3000
pnpm lint             # ESLint
pnpm lint:fix         # ESLint with auto-fix
pnpm typecheck        # tsc --noEmit
pnpm test             # Vitest unit tests
pnpm test:e2e         # Playwright E2E tests (Chromium)
pnpm build            # Production build
```

> **Note:** `pnpm check` (lint + typecheck) currently fails due to an `eslint` directory resolution issue. Use `pnpm lint && pnpm typecheck` instead.

### Pre-Checkin Validation

```bash
# Backend
cd backend && make lint && make test

# Frontend (if changed)
cd frontend && pnpm lint && pnpm typecheck

# Frontend build (if env/auth/routing/build-sensitive changes)
cd frontend && BETTER_AUTH_SECRET=local-dev-secret pnpm build
```

## High-Level Architecture

```
Browser ──▶ Nginx (:2026) ──▶ /api/langgraph/* → Gateway LangGraph runtime (:8001)
                          ──▶ /api/*          → Gateway REST API (:8001)
                          ──▶ /               → Frontend (:3000)
                                   │
                    Gateway (FastAPI + LangGraph agent runtime)
                         ├─ Lead Agent (make_lead_agent)
                         ├─ 18-middleware chain
                         ├─ Sandbox system (local / Docker / Kubernetes)
                         ├─ Subagent delegation (general-purpose, bash)
                         ├─ MCP tools (stdio, SSE, HTTP transports)
                         ├─ Community tools (tavily, jina_ai, firecrawl)
                         └─ IM Channels (Feishu, Slack, Telegram, DingTalk)
```

### Key Architectural Boundaries

1. **Harness vs. App**: `backend/packages/harness/deerflow/` (publishable, `deerflow.*`) vs. `backend/app/` (application, `app.*`). App imports deerflow; deerflow NEVER imports app. Enforced in CI by `tests/test_harness_boundary.py`.

2. **Gateway + Runtime co-location**: The LangGraph agent runtime runs inside the Gateway process (not a separate LangGraph server). Nginx proxies `/api/langgraph/*` → Gateway's embedded runtime and rewrites the prefix to Gateway's native `/api/*` routes.

3. **Config reload boundary**: Most config fields hot-reload on next message (models, tools, memory, summarization). Infrastructure fields require restart — the authoritative list is in `packages/harness/deerflow/config/reload_boundary.py::STARTUP_ONLY_FIELDS`.

4. **Sandbox virtual paths**: Agents see `/mnt/user-data/{workspace,uploads,outputs}` and `/mnt/skills`. These are translated to physical paths on the host or volume-mounted in Docker containers. Always use the virtual paths in agent-facing code.

### Backend Source Layout (key directories)

```
backend/
├── packages/harness/deerflow/   # Harness package (deerflow-harness)
│   ├── agents/                  # Lead agent factory + 18 middlewares + memory + thread state
│   ├── sandbox/                 # Abstract Sandbox, LocalSandboxProvider, bash/ls/read/write tools
│   ├── subagents/               # Subagent registry + executor (general-purpose, bash)
│   ├── tools/builtins/          # present_files, ask_clarification, view_image
│   ├── mcp/                     # MultiServerMCPClient integration (stdio/SSE/HTTP + OAuth)
│   ├── models/                  # Model factory (thinking/vision support, vLLM provider)
│   ├── skills/                  # Skill discovery, loading, parsing (SKILL.md)
│   ├── config/                  # AppConfig, model/sandbox/tool config, reload boundary
│   ├── community/               # tavily, jina_ai, firecrawl, image_search, aio_sandbox
│   ├── reflection/              # Dynamic module loading (resolve_variable, resolve_class)
│   ├── client.py                # Embedded Python client (no HTTP needed)
│   └── utils/                   # Network, readability utilities
├── app/
│   ├── gateway/                 # FastAPI app + routers (models, mcp, skills, memory, threads, etc.)
│   └── channels/                # IM platform bridges (Feishu, Slack, Telegram, DingTalk)
└── tests/                       # pytest suite (also tests/blocking_io/ for blocking-IO gate)
```

### Frontend Source Layout

```
frontend/src/
├── app/               # Next.js App Router (/, /workspace/chats/[thread_id])
├── components/
│   ├── ui/            # Shadcn UI primitives (auto-generated, do not edit)
│   ├── ai-elements/   # Vercel AI SDK elements (auto-generated, do not edit)
│   ├── workspace/     # Chat page components (messages, artifacts, settings)
│   └── landing/       # Landing page sections
├── core/              # Business logic: threads, api, artifacts, i18n, settings, memory, skills, mcp
├── hooks/             # Shared React hooks
├── lib/               # Utilities (cn() from clsx + tailwind-merge)
└── server/            # Server-side code (better-auth, not yet active)
```

### Config Files

| File | Purpose |
|------|---------|
| `config.yaml` (root) | Main app config: models, tools, sandbox, memory, subagents, channels |
| `extensions_config.json` (root) | MCP servers and skills enable/disable state |
| `.env` (root) | Environment variables (gitignored) |
| `backend/langgraph.json` | LangGraph graph entrypoint (`deerflow.agents:make_lead_agent`) |
| `frontend/src/env.js` | Frontend env schema validation (`@t3-oss/env-nextjs` + Zod) |

Config priority: explicit path arg → `DEER_FLOW_CONFIG_PATH` env var → `backend/config.yaml` → root `config.yaml` (recommended). Values starting with `$` are resolved as env vars (e.g., `$OPENAI_API_KEY`).

## Important Gotchas

- **`make config` is non-idempotent**: It intentionally aborts if `config.yaml` already exists. Use `make config-upgrade` to merge new fields.
- **Frontend build needs `BETTER_AUTH_SECRET`**: Set it or use `SKIP_ENV_VALIDATION=1`. Prefer setting a real secret.
- **`pnpm check` is broken**: The `next lint` invocation resolves to an invalid directory. Run `pnpm lint && pnpm typecheck` separately.
- **Proxy env vars** (`HTTP_PROXY`, `HTTPS_PROXY`, etc.) can silently break frontend network operations. Unset them if `pnpm install` fails.
- **Backend strict blocking-IO gate**: Any sync blocking IO in `app.*` or `deerflow.*` on the asyncio event loop fails the test. Offload using `asyncio.to_thread`. CI enforces this.
- **Harness boundary**: `deerflow.*` must never import from `app.*`. CI enforces this.
- **Config caching**: `get_app_config()` caches but auto-reloads on mtime change. Most fields hot-reload; infrastructure fields require restart.

## Documentation

- `backend/CLAUDE.md` — Comprehensive backend architecture, middleware chain, API routes, sandbox, memory, subagent, MCP, and skills system details
- `frontend/CLAUDE.md` — Frontend architecture, component layout, data flow patterns
- `frontend/AGENTS.md` — Frontend agent system architecture and contributing guide
- `.github/copilot-instructions.md` — Validated command sequences and CI parity information
- `docs/` — Feature-specific docs (CONFIGURATION.md, ARCHITECTURE.md, FILE_UPLOAD.md, etc.)
- `Install.md` — Setup instructions for coding agents
