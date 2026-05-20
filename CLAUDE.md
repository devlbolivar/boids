# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Boids AI is a monorepo with a multi-tenant FastAPI backend and a Next.js dashboard.

```
boids-ai/
├── backend/     # FastAPI — M1-M8 (API, workers, DB, Redis)
├── dashboard/   # Next.js — M8 (frontend: dashboard, review queue, campaigns)
└── docs/        # Technical milestone documents
```

---

## Backend (`backend/`)

All backend commands must be run from the `backend/` directory.

### Running the stack

```bash
cd backend
docker compose up --build          # Start all services (API, worker, DB, Redis)
docker compose up db redis         # Start only infrastructure
```

### Running locally (without Docker)

```bash
cd backend
uvicorn app.main:app --reload      # API on :8000
celery -A app.workers.celery_app worker --loglevel=info -Q orchestrator,agents,delivery
```

### Database migrations (Alembic)

```bash
cd backend
alembic upgrade head                              # Apply all migrations
alembic revision --autogenerate -m "description" # Generate migration from model changes
alembic downgrade -1                              # Roll back one migration
```

When generating migrations, all models must be imported in `migrations/env.py` so SQLAlchemy metadata is populated.

### Tests

```bash
cd backend
pytest                                                           # Run all tests (124 pass)
pytest tests/test_auth.py::test_name -v                         # Run a single test
pytest tests/integration/test_dashboard_endpoints.py -v         # M8 backend tests only
make test-m8                                                     # M8 backend + frontend unit tests
```

Tests require a live PostgreSQL instance. They connect to `boids_test_db` (derived from `DATABASE_URL` by replacing `boids_db`). The test database schema is created and torn down automatically per session via `conftest.py`.

The test engine connects as the postgres superuser, which bypasses `FORCE ROW LEVEL SECURITY`. Direct inserts in tests therefore skip RLS — this is intentional so fixtures can seed data for any tenant. Use `get_tenant_db` in application code to enforce isolation at runtime.

### Dependencies

```bash
cd backend
poetry install          # Install all dependencies
poetry add <package>    # Add a new dependency
```

---

## Dashboard (`dashboard/`)

All dashboard commands must be run from the `dashboard/` directory.

### Running locally

```bash
cd dashboard
npm install        # first time only
npm run dev        # dev server on :3000
```

The frontend expects the backend at `http://localhost:8000` by default. Override with the env var `NEXT_PUBLIC_API_URL`.

### Tests

```bash
cd dashboard
npm run test:run   # unit tests (vitest, jsdom)
```

### Pages

| Route | Description |
|---|---|
| `/login` | Auth — stores JWT in localStorage |
| `/register` | Tenant registration |
| `/dashboard` | Metrics (leads/emails/meetings) + funnel chart |
| `/review` | Manual review queue — approve/reject email drafts |
| `/campaigns` | Campaign list with per-step run buttons |

### Key paths

- `app/(app)/` — authenticated layout with sidebar auth guard
- `app/(auth)/` — login and register pages
- `components/dashboard/` — MetricCard, FunnelChart, MeetingsCard, CostCard, DashboardOverview
- `components/review/EmailPreview.tsx` — approve/reject UI with QA score
- `components/campaigns/RunButton.tsx` — triggers campaign step via API
- `lib/api.ts` — axios instance with JWT interceptor and 401 redirect
- `lib/hooks/` — useDashboard, useReviewQueue TanStack Query hooks

---

## Architecture (Backend)

### Multi-tenancy model

Tenant isolation is enforced at the database level using **PostgreSQL Row-Level Security (RLS)**. The `agent_runs` table has an RLS policy that filters rows by `current_setting('app.tenant_id')::UUID`. Isolation is activated per-request by `SET LOCAL app.tenant_id = <id>` at session open time.

The `tenants` table itself has no RLS — it lives in the shared `public` schema and is accessed directly by auth endpoints.

### Two database session dependencies

`app/dependencies.py` exports two session providers that must be used correctly:

- `get_db` — plain session, **no RLS**. Used only by auth endpoints (`/auth/register`, `/auth/token`) that need to query the `tenants` table before a tenant identity is established.
- `get_tenant_db` — sets `app.tenant_id` on the session before yielding. Required for all tenant-scoped endpoints so that RLS policies activate correctly.

Using `get_db` in a tenant endpoint would bypass isolation entirely.

### Auth flow

1. Registration (`POST /auth/register`) creates a `Tenant` row and returns a JWT immediately.
2. Login (`POST /auth/token`) validates credentials and returns a JWT.
3. JWTs carry `{"sub": email, "tenant_id": uuid}` claims encoded with `SECRET_KEY` (HS256).
4. `get_current_tenant` dependency decodes the token and returns `tenant_id` as a string; this value is passed into `get_tenant_db` to scope the session.

### Credential encryption

Sensitive third-party credentials (API keys, etc.) are stored encrypted in the `api_keys_enc` JSONB column on the `Tenant` model. Encryption uses **per-tenant Fernet keys derived via HKDF** from the single `MASTER_ENCRYPTION_KEY` environment variable. The derivation uses the tenant UUID as HKDF `info`, meaning each tenant's key is unique. Helpers live in `app/core/security.py`: `encrypt_credential` / `decrypt_credential`.

### Celery workers

Three named queues exist: `orchestrator`, `agents`, `delivery`. All share the same Redis broker and backend. New tasks must be registered in `celery.conf.include` in `app/workers/celery_app.py` and routed to the correct queue with the `queue=` parameter on `@celery.task`.

### Configuration

All settings are in `app/config.py` via `pydantic-settings`. Values are read from environment variables or a `.env` file. Copy `.env.example` to `.env` to get started locally.

Key variables: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `MASTER_ENCRYPTION_KEY`.

### M8 endpoints

**Dashboard** (`app/dashboard/router.py`) — all require `get_tenant_db` + JWT:

| Endpoint | Description |
|---|---|
| `GET /dashboard/summary` | Lead counts by status, email open/reply rates, meeting totals |
| `GET /dashboard/funnel` | All 8 lead statuses with counts; optional `?campaign_id=` filter |
| `GET /dashboard/meetings/upcoming` | Future scheduled meetings ordered by date |
| `GET /dashboard/cost` | Agent run cost breakdown by type (`lead_finder`, `research`, etc.) |

**Review queue** (`app/review/router.py`):

| Endpoint | Description |
|---|---|
| `GET /review` | Leads in `needs_review` with their latest email draft |
| `POST /review/{lead_id}/approve` | Sets status → `emailed`, fires `send_email.delay()` |
| `POST /review/{lead_id}/reject` | Sets status → `rejected` |

### AgentRun cost model

`AgentRun` lives in `app/tenants/models.py` (not `app/workers/models`). Cost is calculated in `DashboardService.get_cost_summary()` using `AGENT_PRICES` dict keyed by agent type.
