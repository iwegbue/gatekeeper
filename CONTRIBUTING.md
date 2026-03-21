# Contributing to Gatekeeper Core

Thank you for your interest in contributing!
Please read this document and `CLAUDE.md` before opening a PR.

---

## Development Setup

```bash
git clone https://github.com/iwegbue/gatekeeper-core
cd gatekeeper-core
uv sync
cp .env.example .env
# Edit .env — set SECRET_KEY, ADMIN_PASSWORD, POSTGRES_PASSWORD
docker compose up -d
uv run uvicorn app.main:app --reload
```

Running tests requires Postgres (the docker-compose stack includes it):

```bash
SKIP_SECURITY_CHECKS=1 uv run pytest
```

---

## Workflow

### Branch naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/short-description` | `feat/webhook-notifications` |
| Bug fix | `fix/short-description` | `fix/trade-close-journal-null` |
| Security | `security/short-description` | `security/csrf-api-routes` |
| Docs | `docs/short-description` | `docs/update-api-reference` |
| Refactor | `refactor/short-description` | `refactor/extract-scoring-util` |

Always branch off `main`:

```bash
git checkout main && git pull
git checkout -b feat/your-feature
```

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

<optional body — what and why, not how>
```

Types: `feat`, `fix`, `security`, `refactor`, `test`, `docs`, `chore`
Scopes (optional): `ideas`, `trades`, `journal`, `plan`, `api`, `auth`, `db`, `ai`

Examples:
```
feat(api): add webhook endpoint for trade close events
fix(journal): guard against None after tag re-fetch
security(auth): enforce CSRF on all HTML POST routes
test(plan_service): cover update_rule protected fields
```

### Pull Requests

1. Keep PRs **focused** — one feature or fix per PR.
2. All tests must pass: `SKIP_SECURITY_CHECKS=1 uv run pytest`.
3. Update `CHANGELOG.md` — add a line under `[Unreleased]`.
4. Fill in the PR template (see `.github/PULL_REQUEST_TEMPLATE.md` if present).
5. PRs without tests for new service-layer code will not be merged.

---

## Project Structure

```
app/
  auth.py              # Session middleware + bearer token dependency
  config.py            # Pydantic settings + startup security check
  csrf.py              # CSRF token generation / verification
  database.py          # Async SQLAlchemy engine + get_db()
  main.py              # App factory, middleware, router wiring
  models/              # SQLAlchemy ORM models
  routers/             # HTML/HTMX route handlers (thin HTTP layer)
    api/v1/            # JSON API route handlers
  schemas/             # Pydantic request/response models (API only)
  services/            # All business logic (where tests live)
    ai/                # AI provider abstraction
    state_machine.py   # Idea state transitions + guards
  templates/           # Jinja2 HTML templates
alembic/versions/      # DB migrations
tests/
  conftest.py          # DB fixtures, test client, MockProvider
  factories.py         # Test data factories
```

**Rule: routers call services. Services contain all logic. No business logic in routers.**

---

## Writing Tests

Tests run against a real throwaway PostgreSQL schema — no SQLite, no mocking the DB.

```python
from tests.factories import create_plan, create_rule, create_idea, create_trade

@pytest.mark.asyncio
async def test_my_feature(db):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="My rule")
    idea = await create_idea(db)
    # test your service function directly
```

**Key factories:**

| Factory | Creates |
|---------|---------|
| `create_plan(db)` | TradingPlan |
| `create_rule(db, plan_id, layer=, name=, rule_type=, weight=)` | PlanRule |
| `create_idea(db, instrument=, direction=, state=)` | Idea + checks |
| `create_trade(db, idea_id, entry_price=, sl_price=, grade=)` | Trade |
| `create_full_pipeline(db)` | Plan + idea + checks + trade |

**Mock the AI provider — never call real APIs in tests.**

Coverage target: **≥ 80% on `app/services/`**.

```bash
SKIP_SECURITY_CHECKS=1 uv run pytest --cov=app/services --cov-report=term-missing
```

---

## Adding a Feature — Checklist

Before opening a PR, verify:

- [ ] Short spec written (what, why, which files change)
- [ ] DB migration created and tested if schema changes
- [ ] Service function(s) implemented
- [ ] Tests written alongside service code — not after
- [ ] HTML router updated with `_csrf: None = Depends(require_csrf)` on all POST endpoints
- [ ] API router + Pydantic schema added if exposing via JSON API
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] `SKIP_SECURITY_CHECKS=1 uv run pytest` passes locally

---

## Migrations

```bash
# Create a new migration
uv run alembic revision -m "short_description"
# Edit alembic/versions/NNN_short_description.py

# Apply
uv run alembic upgrade head

# Roll back one step
uv run alembic downgrade -1
```

Always implement both `upgrade()` and `downgrade()`.
Name migrations sequentially: `003_add_webhook_table`, `004_add_rule_tags`.

---

## Code Style

- Python 3.12+ — use `X | Y` unions, not `Optional[X]`
- Type hints on all function signatures
- `async def` for everything that touches the DB
- No `print()` in application code — use `logging.getLogger(__name__)`
- No bare `except Exception` — catch specific exceptions or log unexpected ones
- `hmac.compare_digest()` for any credential/token comparison — never `==`

---

## Security Rules

These are non-negotiable:

1. All HTML `POST` routes must have `_csrf: None = Depends(require_csrf)`.
2. All HTML forms must include `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.
3. Never render secrets (API keys, tokens) into HTML templates.
4. Validate any user-supplied URLs against an allowlist.
5. Use `hmac.compare_digest()` for credential comparisons.

---

## License

By contributing, you agree your changes will be licensed under [AGPL-3.0](LICENSE).
