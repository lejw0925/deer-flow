# Repository Guidelines

Guidance for AI coding agents (Claude Code, Codex, and others) working in this repository. The sibling `CLAUDE.md` only imports this file via `@AGENTS.md` — edit here, not there. Module-level guidance lives in `backend/AGENTS.md` (the detailed source of truth for backend internals) and `frontend/AGENTS.md`; read the relevant one before changing that module.

## Project Overview

DeerFlow (Deep Exploration and Efficient Research Flow) 2.0 is an open-source **super agent harness** built on LangGraph. It orchestrates sub-agents, long-term memory, sandboxed code execution, and extensible skills. Version 2.0 is a ground-up rewrite that shares no code with the v1 Deep Research framework (maintained on the `main-1.x` branch upstream).

This is a full-stack monorepo with four runtime services:

- **Gateway API** (port 8001): FastAPI REST API plus an embedded LangGraph-compatible agent runtime (`RunManager` + `run_agent()` + `StreamBridge` in `backend/packages/harness/deerflow/runtime/`).
- **Frontend** (port 3000): Next.js web interface.
- **Nginx** (port 2026): unified reverse-proxy entry point. Routes `/api/langgraph/*` to the Gateway runtime (rewritten to `/api/*`), other `/api/*` to Gateway REST, and everything else to the frontend.
- **Provisioner** (port 8002, optional): sandbox provisioning, started only when sandbox is configured for provisioner/Kubernetes mode. Redis backs the cross-process SSE stream bridge in Docker deployments.

**Toolchain requirements**: Python 3.12+ (managed with `uv`), Node.js 22+, pnpm 10.26.2+. Docker for containerized runs and the sandbox.

## Project Structure & Module Organization

```
deer-flow/
├── Makefile                  # Root commands (setup, install, dev, stop, up/down)
├── config.yaml               # Main app config (from config.example.yaml; never commit)
├── extensions_config.json    # MCP servers and skills config (never commit)
├── backend/                  # Python 3.12 backend (uv workspace)
│   ├── packages/harness/     # deerflow-harness: publishable agent framework
│   │   └── deerflow/         #   import as deerflow.* (agents, sandbox, subagents,
│   │                         #   tools, mcp, skills, models, config, memory, runtime, tui)
│   ├── app/                  # Unpublished application code, import as app.*
│   │   ├── gateway/          #   FastAPI Gateway (app.py + routers/)
│   │   ├── channels/         #   IM integrations (Feishu, Slack, Telegram, DingTalk, ...)
│   │   └── scheduler/        #   Scheduled tasks
│   ├── tests/                # pytest suite (flat test_<behavior>.py files)
│   ├── scripts/ docs/ samples/
│   └── pyproject.toml        # Backend deps; uv workspace includes packages/harness
├── frontend/                 # Next.js 16 / React 19 / TypeScript app
│   ├── src/                  # app/ (App Router), components/, core/ (business logic), hooks/, lib/
│   └── tests/                # unit/ (Rstest) and e2e/ (Playwright)
├── contracts/                # Shared JSON contracts (run event stream, slash skill, ...)
├── skills/                   # public/ (committed agent skills) and custom/ (gitignored)
├── tests/skills/             # Root-level skill tests
├── scripts/                  # Repo tooling (setup wizard, doctor, serve.sh, docker.sh, ...)
├── docker/                   # Dockerfiles, docker-compose files, nginx config
├── deploy/helm/              # Helm chart for Kubernetes deployment
└── docs/                     # Design docs, plans, upstream merge notes
```

**Harness / app split** (backend): `app.*` may import `deerflow.*`, but `deerflow.*` must never import `app.*`. This boundary is enforced in CI by `backend/tests/test_harness_boundary.py`.

## Build, Test, and Development Commands

From the repository root:

```bash
make setup         # Interactive setup wizard (recommended; writes config.yaml and .env)
make install       # Install backend (uv sync), frontend (pnpm install), pre-commit hooks
make config        # Create local config files from the examples (aborts if they exist)
make config-upgrade# Merge new fields from config.example.yaml into config.yaml
make doctor        # Validate configuration and required tools
make check         # Check required tools are installed
make dev           # Run the full hot-reloading stack (public entry: http://localhost:2026)
make stop          # Stop all services
make up / make down# Build/start and stop production Docker services (localhost:2026)
make docker-start  # Docker development environment (mode-aware from config.yaml)
make setup-sandbox # Pre-pull the sandbox container image (recommended)
```

Backend-only, from `backend/`:

```bash
make install            # uv sync
make dev                # Gateway API with reload (port 8001)
make test               # Full pytest suite
make test-blocking-io   # Strict Blockbuster runtime gate on tests/blocking_io/
make lint               # ruff check + ruff format --check
make format             # ruff check --fix + ruff format
make migrate-rev MSG="..."  # Autogenerate an alembic revision
```

Frontend-only, from `frontend/`:

```bash
pnpm dev        # Dev server with Turbopack (port 3000)
pnpm check      # ESLint + TypeScript validation (run before committing)
pnpm test       # Unit tests with Rstest
pnpm test:e2e   # Playwright E2E tests (Chromium)
pnpm format     # Prettier check (format:write to apply)
```

The Gateway auto-applies `alembic upgrade head` at startup; there is intentionally no `migrate` target. Pre-commit hooks (ruff, uv-lock check, ESLint, Prettier) run from `.pre-commit-config.yaml`.

## Coding Style & Naming Conventions

Follow existing local patterns; keep diffs minimal and scoped.

- **Python**: four-space indentation, double quotes, Ruff import ordering and formatting (line length 240, see `backend/ruff.toml`), `snake_case` functions/modules, `PascalCase` classes. Python 3.12+ with type hints.
- **TypeScript**: `@/*` path alias maps to `frontend/src/*`; `PascalCase` components, `camelCase` variables/hooks; prefix intentionally unused values with `_`; enforced import ordering (builtin → external → internal → parent → sibling) with inline type imports; use `cn()` from `@/lib/utils` for conditional Tailwind classes.
- **Generated code**: do not hand-edit `frontend/src/components/ui/` or `frontend/src/components/ai-elements/` (generated from Shadcn, MagicUI, React Bits, and Vercel AI SDK registries; ESLint-ignored).
- **Blocking IO**: backend async paths must keep blocking filesystem/subprocess work off the event loop (`asyncio.to_thread`, `deerflow.utils.file_io.run_file_io`). `make detect-blocking-io` (root or backend) inventories candidates; regression anchors live in `backend/tests/blocking_io/` and run as a hard-fail CI gate.

## Testing Guidelines

- **Tests are mandatory** for features and bug fixes (backend policy: TDD, no exceptions). Run the narrowest relevant test during development, then the module-level suite before review.
- **Backend**: pytest in `backend/tests/`, named `test_<behavior>.py`, mostly flat. Markers: `no_auto_user`, `allow_blocking_io`, `integration` (external services; skipped when unavailable). `tests/blocking_io/` is a strict Blockbuster runtime gate against blocking IO on the event loop.
- **Frontend**: Rstest unit tests under `tests/unit/` mirroring `src/` paths. `*.test.ts(x)` run in node (default, pure logic); `*.dom.test.ts(x)` run in happy-dom (hooks/components) — keep the split, the DOM environment is ~3x slower. Playwright E2E in `tests/e2e/` mocks backend APIs via `page.route()` unless the suite explicitly targets a real backend.
- **Contracts**: run-event stream changes must keep producer code, `deerflow/constants.py`, `runtime/events/catalog.py`, `contracts/run_event_stream_contract.json`, `backend/docs/RUN_EVENT_STREAM.md`, and `tests/test_run_event_stream_contract.py` in sync.
- CI runs backend unit tests, the blocking-IO gate, frontend unit tests, and E2E tests on every PR (see `.github/workflows/`).

## Configuration

- `config.yaml` (project root) is the main configuration; start from `config.example.yaml`. `config.example.yaml` carries a `config_version` — bump it when changing the schema; `make config-upgrade` merges new fields. Values starting with `$` resolve from environment variables (e.g. `$OPENAI_API_KEY`).
- Config resolution order: explicit path → `DEER_FLOW_CONFIG_PATH` → `backend/config.yaml` → root `config.yaml` (recommended). Same pattern for `extensions_config.json` with `DEER_FLOW_EXTENSIONS_CONFIG_PATH`.
- Most per-run fields (`models`, `tools`, `summarization`, `memory`, `subagents`, ...) hot-reload on the next message. Infrastructure fields (`database`, `sandbox`, `run_events`, `stream_bridge`, `channels`, `scheduler`, ...) are restart-required; the authoritative list is `STARTUP_ONLY_FIELDS` in `backend/packages/harness/deerflow/config/reload_boundary.py`.
- **Never commit** `config.yaml`, `extensions_config.json`, `.env`, credentials, or tokens. Document any new configuration field or migration in the same change.

## Security Considerations

- **Sandbox isolation**: shell execution runs in containers with `AioSandboxProvider`. With the local provider, host `bash` is disabled by default — re-enable only for fully trusted local workflows. `execute_command` scrubs secret-looking environment variables (`*KEY*`/`*SECRET*`/`*TOKEN*`/`*PASS*`/`*CREDENTIAL*`) so platform credentials never leak into skill subprocesses.
- **Auth**: browser sessions use Gateway-owned `HttpOnly access_token` + readable `csrf_token` double-submit cookies; the frontend must never store passwords or tokens. CORS is same-origin by default through nginx; split origins require explicit `GATEWAY_CORS_ORIGINS`.
- **Web surface**: active artifact content types (HTML, SVG) are force-served as download attachments to reduce XSS risk; agentic browser navigation is SSRF-screened; the GitHub webhook route is fail-closed without `GITHUB_WEBHOOK_SECRET`.
- Multi-worker Gateway (`GATEWAY_WORKERS > 1`) is rejected when browser control is configured, because browser sessions are process-local.

## Deployment

- **Docker (recommended for production)**: `make up` builds and starts the compose stack in `docker/` (nginx, frontend, gateway, redis, optional provisioner/browserless/jina-reader) on `localhost:2026`; `make down` stops it. Docker defaults to the Redis stream bridge.
- **Local development**: `make dev` (foreground) or `make dev-daemon` via `scripts/serve.sh`.
- **Kubernetes**: Helm chart in `deploy/helm/deer-flow/` (see its README and `values.yaml`).
- Release process: see `RELEASING.md`.

## Commits, Pull Requests, and Documentation

- Commit subjects follow Conventional Commit style, e.g. `fix(runtime): prevent duplicate event writes`. Keep commits focused and imperative. PRs explain the behavior change, link issues, list verification commands, and include screenshots for UI changes.
- **Documentation policy**: keep docs synchronized with code changes — update `README.md` for user-facing changes and the relevant `AGENTS.md` for architecture, command, or workflow changes. Backend details (middleware chain, RunManager/RunStore contract, sandbox/subagent/memory/skills systems, routers) are documented in `backend/AGENTS.md` and `backend/docs/`; frontend data flow and interaction ownership in `frontend/AGENTS.md`.
