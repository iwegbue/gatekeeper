# CLAUDE.md — Gatekeeper Core

This file tells Claude Code how this project works and what conventions to follow.
Read it in full before making any changes.

---

## Project Overview

Gatekeeper Core is a **single-user trading discipline platform**.
It enforces a 7-layer rule-based trading plan via a layer-gated state machine.
The stack is: FastAPI + SQLAlchemy async + PostgreSQL + Jinja2/HTMX.
There is also a JSON API layer under `/api/v1` for CLI/MCP/agent access.

---

## Architecture Rules

### Layer boundaries — strict

```
HTTP layer (routers/)     →  calls services only
Service layer (services/) →  calls models + other services; no HTTP concepts
Model layer (models/)     →  SQLAlchemy ORM; no business logic
Schema layer (schemas/)   →  Pydantic I/O for the JSON API only
```

- **Routers are thin.** No business logic in routers — fetch, call service, return response.
- **Services are the source of truth.** All domain logic lives in `app/services/`.
- **No SQLAlchemy queries in routers.** Always go through a service function.
- **No `request` objects in services.** Services receive plain Python values, not HTTP types.

### Database

- All models use UUID primary keys (`uuid.uuid4`).
- All timestamps are `DateTime(timezone=True)`.
- Enums are stored as strings in Postgres (not native PG enums) — easier migrations.
- Always use `await db.flush()` inside services (not `commit()`). Routers and `get_db()` handle commit.
- `async/await` everywhere — no sync DB calls.

### State machine

The idea state machine in `app/services/state_machine.py` is the core domain constraint.
- Never mutate `idea.state` directly outside `state_machine.py`.
- `GuardError` = layer requirements not met → HTTP 409.
- `TransitionError` = invalid transition → HTTP 409.

### JSON API

- All endpoints live under `/api/v1/` in `app/routers/api/v1/`.
- All are protected by `verify_api_token` bearer dependency (except `POST /api/v1/auth/token`).
- Request/response shapes are defined in `app/schemas/` — never use ORM objects directly in responses.
- Use `model_config = ConfigDict(from_attributes=True)` on all response schemas.

### HTML routes

- All POST routes must include `_csrf: None = Depends(require_csrf)`.
- Templates receive a `csrf_token` automatically via `_TemplateAdapter.TemplateResponse`.
- Every `<form method="post">` must include `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.

### Security

- **Never compare passwords/tokens with `==` or `!=`** — always use `hmac.compare_digest()`.
- **Never render API keys or tokens into HTML** — mask or omit them.
- **Never accept unconstrained URLs from user input** — validate against an allowlist (see `_validate_ollama_url`).
- The startup guard in `app/config.py` rejects insecure defaults. Add `SKIP_SECURITY_CHECKS=1` to `.env` for local dev.

---

## Development Workflow

### For every new feature

1. **Spec first** — write a short description of what changes and why before touching code.
   For larger features, create a plan file (e.g. `docs/plans/FEATURE_NAME.md`).
2. **Migration if needed** — create `alembic/versions/NNN_description.py` before writing service code.
3. **Service first** — implement and test the service layer before writing any router.
4. **Tests alongside** — write tests as you write service code, not after.
5. **Router last** — wire the HTTP layer once the service is solid and tested.
6. **Schema for API endpoints** — add Pydantic schemas to `app/schemas/` for any new API route.

### Running tests

```bash
# All tests (requires Postgres running — see docker-compose.yml or tests/docker-compose.test.yml)
SKIP_SECURITY_CHECKS=1 uv run pytest

# Service coverage report
SKIP_SECURITY_CHECKS=1 uv run pytest --cov=app/services --cov-report=term-missing

# Single file
SKIP_SECURITY_CHECKS=1 uv run pytest tests/test_idea_service.py -v
```

Tests run against a **real throwaway Postgres schema** — no SQLite, no mocking the DB.
Mock only the AI provider (`MockProvider` in test fixtures).

### Migrations

```bash
# Create
uv run alembic revision -m "short_description"
# Edit the generated file in alembic/versions/

# Apply
uv run alembic upgrade head

# Rollback one
uv run alembic downgrade -1
```

Revision IDs follow the format `NNN_description` (e.g. `003_add_notifications_table`).
Always implement both `upgrade()` and `downgrade()`.

### Local dev

```bash
cp .env.example .env
# Edit .env: set SECRET_KEY, ADMIN_PASSWORD, POSTGRES_PASSWORD

docker compose up -d
uv run uvicorn app.main:app --reload
```

Or use the full stack:
```bash
docker compose up
```

---

## Code Conventions

### Python

- Python 3.12+ — use `X | Y` union types, not `Optional[X]`.
- Type hints on all function signatures.
- `async def` everywhere that touches the DB.
- No bare `except Exception` — catch specific exceptions or log unexpected ones.
- No `print()` in application code — use `logging.getLogger(__name__)`.

### Naming

| Thing | Convention |
|-------|-----------|
| Service functions | `verb_noun` — `get_idea`, `create_rule`, `toggle_check` |
| Router functions | `noun_verb` — `idea_detail`, `trade_close` |
| Schema classes | `NounVerb` or `NounResponse` — `IdeaCreate`, `TradeResponse` |
| DB columns | `snake_case` |
| Enums | `UPPER_CASE` values stored as strings |

### Error handling in routers

HTML routers: redirect with `?msg=...&msg_type=error` on failures — no exceptions exposed.
API routers: raise `HTTPException` with appropriate status codes:

| Condition | Status |
|-----------|--------|
| Not found | 404 |
| Guard/transition error | 409 |
| Validation / bad input | 422 |
| Unauthorized | 401 |

---

## Adding a Feature — Checklist

- [ ] Short spec written (what, why, which files)
- [ ] DB migration created (if schema changes)
- [ ] Service function(s) implemented
- [ ] Service tests written and passing
- [ ] HTML router updated (with CSRF)
- [ ] API router updated (with schema)
- [ ] Pydantic schema added/updated
- [ ] `CHANGELOG.md` updated
- [ ] All 175+ tests still pass

---

## File Map (key paths)

```
app/
  auth.py              # Session middleware + bearer token dependency
  config.py            # Pydantic settings + startup security check
  csrf.py              # CSRF token generation and verification
  database.py          # Async SQLAlchemy engine + get_db()
  main.py              # App factory, middleware, router registration
  models/              # SQLAlchemy ORM models
  routers/             # HTML/HTMX route handlers
    api/v1/            # JSON API route handlers
  schemas/             # Pydantic request/response models (API only)
  services/            # All business logic
    ai/                # AI provider abstraction (factory, base, providers)
    state_machine.py   # Idea state transitions + guards
  templates/           # Jinja2 HTML templates
alembic/versions/      # DB migrations
tests/                 # Pytest suite
  conftest.py          # DB fixtures, test client, factories
  factories.py         # Test data factories
```

---

## What NOT to do

- Don't put business logic in routers.
- Don't call `db.commit()` inside services — only `db.flush()`.
- Don't use `select *` — always select specific columns or the full model.
- Don't bypass the state machine to set `idea.state` directly.
- Don't add optional features behind `if settings.X` flags — keep the codebase simple.
- Don't add `try/except` around everything — only catch errors you can meaningfully handle.
- Don't render secret values (API keys, tokens) into HTML templates.
