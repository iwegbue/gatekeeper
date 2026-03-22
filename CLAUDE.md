# CLAUDE.md — Gatekeeper Core

This file tells Claude Code how this project works and what conventions to follow.
Read it in full before making any changes.

---

## Project Overview

Gatekeeper Core is a **single-user trading discipline platform**.
It enforces 7-layer rule-based trading plans via a layer-gated state machine.
Multiple plans can exist but only one is active at a time — new ideas use the active plan.
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

- **Never compare passwords/tokens with `==` or `!=`** — use `hmac.compare_digest()` for secrets; plain `!=` is fine for non-secret equality (e.g. confirming two user-supplied fields match).
- **Never store passwords in plaintext** — use `set_admin_password` / `verify_admin_password` in `settings_service.py` (scrypt hash stored in DB).
- **Never render API keys or tokens into HTML** — mask or omit them.
- **Never accept unconstrained URLs from user input** — validate against an allowlist (see `_validate_ollama_url`).
- `app/config.py` auto-generates `SECRET_KEY` on first run (persisted to `/data/secret_key`). It logs a warning but never aborts if the key is ephemeral. Add `SKIP_SECURITY_CHECKS=1` to `.env` to silence the warning in dev/test.

---

## Development Workflow

### Branch and PR — always

**Never commit directly to `main`.** Every change, no matter how small, goes through a feature branch and a pull request. This applies to human contributors and AI agents alike — if you are an AI agent making changes, you must create a branch before touching any code.

```bash
# Start every feature this way
git checkout main && git pull
git checkout -b feat/short-description   # or fix/, security/, docs/, refactor/
```

Branch naming: `feat/`, `fix/`, `security/`, `docs/`, `refactor/` followed by a short slug (e.g. `feat/webhook-notifications`).

When the work is done:
```bash
git add <files>
git commit -m "feat(scope): short summary"
gh pr create --title "feat(scope): short summary" --body "$(cat <<'EOF'
## Summary
- What changed and why

## Test plan
- [ ] Existing tests pass: `SKIP_SECURITY_CHECKS=1 uv run pytest`
- [ ] New service tests written
- [ ] CHANGELOG.md updated under [Unreleased]
EOF
)"
```

### For every new feature

1. **Branch first** — `git checkout -b feat/name` before touching any code.
2. **Spec first** — write a short description of what changes and why before touching code.
   For larger features, create a plan file (e.g. `docs/plans/FEATURE_NAME.md`).
3. **Migration if needed** — create `alembic/versions/NNN_description.py` before writing service code.
4. **Service first** — implement and test the service layer before writing any router.
5. **Tests alongside** — write tests as you write service code, not after.
6. **Router last** — wire the HTTP layer once the service is solid and tested.
7. **Schema for API endpoints** — add Pydantic schemas to `app/schemas/` for any new API route.
8. **PR** — open a pull request; do not merge directly.

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
# Full stack — no .env editing required
docker compose up -d
# Visit http://localhost — you'll be redirected to /setup on first run

# Or: app on host, DB in Docker
docker compose up -d db
export DATABASE_URL=postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper
export SKIP_SECURITY_CHECKS=1
uv run uvicorn app.main:app --reload
```

### Applying changes to the running Docker stack

The app runs as a built Docker image — code changes on disk are **not** automatically picked up. After any code change that needs to be visible at http://localhost, always run these three steps in order:

```bash
# 1. Rebuild the app image from the current branch
docker compose build app

# 2. Run any new migrations against the live database
docker compose run --rm app uv run alembic upgrade head

# 3. Recreate the container with the new image
docker compose up -d app
```

If there are no schema changes (no new migration), skip step 2.
Check `docker compose logs app --tail=20` to confirm the app started cleanly after step 3.

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
- [ ] All 300+ tests still pass
- [ ] **Help section reviewed** — if the feature adds or changes UI, update `app/templates/help/index.html` to reflect it
- [ ] **VISION.md reviewed** — if the feature affects product direction, roadmap status, or Core/Pro boundaries, update `VISION.md` to reflect it

### Help section (`/help`)

The help page at `app/templates/help/index.html` is the single source of in-app documentation. It must stay accurate as the product evolves.

**Update the help section when you:**
- Add a new page, section, or workflow to the UI
- Rename, move, or remove a feature
- Change how a core concept works (state transitions, rule types, grading, scoring)
- Add new AI capabilities, API endpoints, or CLI commands
- Change navigation (sidebar links, top-bar icons)

**Do not update the help section for:**
- Internal refactors with no user-visible change
- Bug fixes that restore existing documented behaviour
- Styling or layout tweaks that don't affect how a feature works

The help page is a static Jinja2 template — no service or router logic required. Edit it directly and rebuild the Docker image to see changes.

### Vision and roadmap (`VISION.md`)

`VISION.md` is the product direction document. It defines what Gatekeeper is, the Core/Pro split, design principles, and the roadmap horizon. Keep it accurate as the product evolves.

**Update VISION.md when you:**
- Ship a roadmap item — move it from its horizon into the "Now" section or mark it as delivered
- Add a feature that changes the Core/Pro boundary (e.g. something previously "Planned for Pro" lands in Core)
- Add a capability that belongs in the "Category" section (what Gatekeeper is or is not)
- Cut or defer a roadmap item — remove or move it honestly
- Release a new version — update the "Now" section to reflect the current state

**Do not update VISION.md for:**
- Internal refactors with no user-visible change
- Bug fixes that restore existing documented behaviour
- Features already captured in the roadmap that are simply being implemented

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
