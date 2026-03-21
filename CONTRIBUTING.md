# Contributing to Gatekeeper Core

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/your-org/gatekeeper-core
cd gatekeeper-core
uv sync
cp .env.example .env
docker compose -f tests/docker-compose.test.yml up -d
uv run pytest
```

## Project Structure

- `app/models/` — SQLAlchemy ORM models
- `app/services/` — Business logic (where most tests live)
- `app/routers/` — FastAPI route handlers (thin HTTP layer)
- `app/templates/` — Jinja2 + HTMX HTML templates
- `tests/` — Pytest test suite

## Writing Tests

Tests use a real PostgreSQL instance (not SQLite). Each test gets a fresh schema that is created before and dropped after — no shared state.

**Quick factory pattern:**

```python
from tests.factories import create_plan, create_rule, create_idea

@pytest.mark.asyncio
async def test_my_feature(db):
    plan = await create_plan(db)
    rule = await create_rule(db, plan.id, layer="CONTEXT", name="My rule")
    idea = await create_idea(db)
    # ... test your service ...
```

**Key factories:**

| Factory | What it creates |
|---|---|
| `create_plan(db)` | TradingPlan |
| `create_rule(db, plan_id, layer=, name=, rule_type=, weight=)` | PlanRule |
| `create_idea(db, instrument=, direction=, state=)` | Idea |
| `create_idea_with_checks(db, plan_id)` | Idea + IdeaRuleCheck list |
| `create_trade(db, idea_id, entry_price=, sl_price=, grade=)` | Trade |
| `create_full_pipeline(db)` | Everything — plan + idea + checks + trade |

**Focus on services, not routers.** Router tests are only needed for auth and critical flows. The business logic that matters lives in `app/services/`.

**No mocking the database.** Tests run against a real (throwaway) Postgres instance. This validates SQL correctness, JSONB queries, and asyncpg behavior.

**Mock the AI provider.** AI service tests use a `MockProvider` — never call real APIs in tests.

## Coverage

Aim for >= 80% coverage on `app/services/`. Run:

```bash
uv run pytest --cov=app/services --cov-report=term-missing
```

## Pull Requests

1. Fork + create a branch
2. Write tests first (or alongside) — don't submit untested code
3. Run `uv run pytest` — all tests must pass
4. Keep PRs focused — one feature or fix per PR
5. Update `CHANGELOG.md` with a one-line summary

## Code Style

- Python 3.12 type hints throughout
- `async/await` everywhere — no sync DB calls
- UUID primary keys on all models
- Enums stored as strings in Postgres
- Services return domain objects, not HTTP responses

## License

By contributing, you agree your changes will be licensed under [AGPL-3.0](LICENSE).
