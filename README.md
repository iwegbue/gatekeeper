# Gatekeeper Core

**A trading discipline platform for rule-based traders.**

Define your trading plan as a set of rules across 7 decision layers. Every idea you evaluate runs through your personal checklist. You can only open a trade when all required rules are checked off. After closing, your journal captures how well you followed the plan.

Bring your own AI key (Anthropic, OpenAI, or Ollama) for plan-building assistance and post-trade coaching.

---

## Features

- **Multiple trading plans** — define rules across 7 layers (CONTEXT → SETUP → CONFIRMATION → ENTRY → RISK → MANAGEMENT → BEHAVIORAL); multiple plans supported, one active at a time
- **Layer-gated state machine** — ideas cannot advance without completing their layer's required rules
- **Weighted checklist grading** — A/B/C grades based on rule weights; advisory rules visible but non-blocking
- **Trade management** — partials, BE lock, SL updates, R-multiple computed on close
- **Auto-journal** — post-mortem entry created automatically on trade close, capturing plan adherence %
- **AI plan builder** — multi-turn wizard to convert your strategy into structured rules (BYOK)
- **AI idea review** — analyzes your checklist state against the plan
- **AI journal coach** — reviews post-mortem entries and identifies behavioral patterns
- **Discipline reports** — discipline score, rule violation frequency, grade distribution, adherence trend
- **HTMX UI** — responsive, server-rendered frontend; no JavaScript build step required
- **Single-user** — designed for personal use; one instance per trader

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg
- **Database**: PostgreSQL 16
- **Frontend**: Jinja2, HTMX, Pico CSS
- **AI**: Anthropic / OpenAI / Ollama (BYOK — keys stored in DB, no restart needed)
- **Package manager**: uv
- **Migrations**: Alembic

---

## Quick Start

### Prerequisites

- Docker + Docker Compose

### 1. Clone and start

```bash
git clone https://github.com/iwegbue/gatekeeper
cd gatekeeper
docker compose up -d
```

That's it. No `.env` editing required.

### 2. Complete first-run setup

Navigate to **http://localhost** — you'll be redirected to the setup wizard automatically.
Set your admin password and you're in.

A strong `SECRET_KEY` is auto-generated on first run and persisted to the `appdata` Docker
volume so sessions survive container restarts.

### 4. Set up your plan

1. Go to **Trading Plans** → create or select a plan, then add rules across the 7 layers
2. Go to **Instruments** → add the markets you trade
3. Go to **Settings** → optionally configure your AI provider (BYOK)

### 5. Start trading

1. **Create an idea** for a setup you're watching
2. **Work through the checklist** — tick rules as conditions are met
3. **Advance through states** — WATCHING → SETUP_VALID → CONFIRMED → ENTRY_PERMITTED
4. **Open a trade** when ENTRY_PERMITTED
5. **Manage and close** — journal is auto-created on close
6. **Review** — complete the journal entry, check your **Reports**

---

## AI Setup (BYOK)

Go to **Settings** and configure your provider:

| Provider | Setting |
|---|---|
| Anthropic | Paste your API key (claude-sonnet-4-6 default) |
| OpenAI | Paste your API key (gpt-4o default) |
| Ollama | Enter your base URL (http://localhost:11434) |

You can also set `ANTHROPIC_API_KEY` as an env var in `.env` as a boot-time fallback.

---

## Development

```bash
# Install dependencies
uv sync

# Run tests (requires Docker for Postgres)
docker compose -f tests/docker-compose.test.yml up -d
uv run pytest

# Check coverage
uv run pytest --cov=app/services --cov-report=term-missing

# Run locally (no Docker)
export DATABASE_URL=postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper
uv run uvicorn app.main:app --reload
```

### Running tests

Tests use a throwaway Postgres container on port 5433. Each test gets a fresh schema (create_all/drop_all), so they are fully isolated and never pollute each other.

```bash
# Start test DB
docker compose -f tests/docker-compose.test.yml up -d

# Run all tests
uv run pytest

# Run a specific module
uv run pytest tests/test_state_machine.py -v
```

---

## Architecture

```
app/
├── models/          # SQLAlchemy ORM models (UUID PKs, async)
├── services/        # Business logic (service layer, no HTTP)
│   ├── ai/          # BYOK AI providers (Anthropic, OpenAI, Ollama)
│   ├── checklist_service.py   # Scoring, grading, layer completion
│   ├── state_machine.py       # Layer-gated transitions
│   ├── trade_service.py       # R-multiple, plan adherence
│   └── ...
├── routers/         # FastAPI routers (thin HTTP layer)
├── templates/       # Jinja2 + HTMX templates
├── tasks/           # Background loops
└── main.py          # App factory + lifespan

tests/
├── conftest.py      # Per-test async DB engine (function scope)
├── factories.py     # Test object helpers
└── test_*.py        # Service-layer tests
```

### State Machine

```
WATCHING → SETUP_VALID → CONFIRMED → ENTRY_PERMITTED → IN_TRADE → MANAGED → CLOSED
Any non-terminal → INVALIDATED
```

Advancement requires all REQUIRED rules in the current layer to be checked. Backward regression is allowed before IN_TRADE.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

[AGPL-3.0](LICENSE)
