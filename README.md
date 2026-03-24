# Gatekeeper Core

**A trading discipline platform for rule-based traders.**

Define your trading plan as a set of rules across 7 decision layers. Every idea you evaluate runs through your personal checklist. You can only open a trade when all required rules are checked off. After closing, your journal captures how well you followed the plan.

Bring your own AI key (Anthropic, OpenAI, or Ollama) for plan-building assistance and post-trade coaching.

---

## Features

- **Multiple trading plans** — define rules across 7 layers (Context → Setup → Confirmation → Entry → Risk → Management → Behavioral); multiple plans supported, one active at a time
- **Layer-gated state machine** — ideas cannot advance without completing their layer's required rules
- **Weighted checklist grading** — A/B/C grades based on rule weights; advisory rules visible but non-blocking
- **Trade management** — partial exits, breakeven lock, stop loss updates, R-multiple computed on close
- **Auto-journal** — post-mortem entry created automatically on trade close, capturing plan adherence %
- **AI plan builder** — multi-turn wizard to convert your strategy into structured rules (BYOK)
- **AI idea review** — analyzes your checklist state against the plan
- **AI journal coach** — reviews post-mortem entries and identifies behavioral patterns
- **Discipline reports** — discipline score, rule violation frequency, grade distribution, adherence trend
- **Single-user** — designed for personal use; one instance per trader

---

## Installation

Gatekeeper runs as a self-hosted web app on your own computer. You access it through your browser at `http://localhost`.

> **What you'll need before starting:**
> - **Docker Desktop** — the software that runs Gatekeeper. Free download at [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop). ~700MB. Requires a restart on Windows.
> - **Git** — to download the Gatekeeper files. Usually pre-installed on Mac. Windows users: download at [git-scm.com](https://git-scm.com/downloads).
> - A terminal (Terminal on Mac, Command Prompt or PowerShell on Windows).

### Step 1 — Install Docker Desktop

Download and install Docker Desktop for your platform. Once installed, open it and wait for it to finish starting (you'll see the Docker whale icon in your menu bar / system tray).

Docker Desktop must be running every time you want to use Gatekeeper.

### Step 2 — Download Gatekeeper

Open a terminal and run:

```bash
git clone https://github.com/iwegbue/gatekeeper
cd gatekeeper
```

This downloads the Gatekeeper files into a folder called `gatekeeper`.

If you don't want to use git, you can also [download a ZIP from GitHub](https://github.com/iwegbue/gatekeeper/archive/refs/heads/main.zip), unzip it, and open a terminal in that folder.

### Step 3 — Start Gatekeeper

```bash
docker compose up -d
```

This pulls and starts three containers (the app, the database, and a web server). The first run downloads ~500MB of images — this only happens once.

### Step 4 — Open the app

Navigate to **[http://localhost](http://localhost)** in your browser.

You'll be redirected to the setup wizard automatically. Set your admin password and you're in. The whole setup takes about 2 minutes.

---

## Daily use

### Starting Gatekeeper

Make sure Docker Desktop is open and running, then:

```bash
cd gatekeeper
docker compose up -d
```

Then open **[http://localhost](http://localhost)**.

### Stopping Gatekeeper

```bash
docker compose down
```

Your data is saved in a Docker volume and is not affected by stopping or starting.

### Checking if it's running

```bash
docker compose ps
```

All three services (db, app, nginx) should show as `running`.

---

## Updating Gatekeeper

When a new version is released:

```bash
cd gatekeeper
git pull
docker compose build app
docker compose run --rm app uv run alembic upgrade head
docker compose up -d app
```

What each step does:
1. `git pull` — downloads the new code
2. `docker compose build app` — rebuilds the app image with the new code
3. `alembic upgrade head` — applies any database changes
4. `docker compose up -d app` — restarts the app with the new image

If there are no database changes in the release notes, you can skip step 3.

---

## Backing up your data

All your data (trades, ideas, journal entries, plan rules) lives in a Docker volume called `gatekeeper_pgdata`. To back it up:

```bash
docker compose exec db pg_dump -U gatekeeper gatekeeper > gatekeeper-backup-$(date +%Y%m%d).sql
```

This creates a file like `gatekeeper-backup-20260324.sql` in your current folder.

**To restore from a backup:**

```bash
# Stop the app first
docker compose down

# Start only the database
docker compose up -d db

# Restore
cat gatekeeper-backup-20260324.sql | docker compose exec -T db psql -U gatekeeper gatekeeper

# Start everything back up
docker compose up -d
```

---

## Forgotten password

If you forget your admin password, you can reset it using the `ADMIN_PASSWORD` environment variable.

**Option 1 — Reset via environment variable (recommended):**

1. Open `.env` in the `gatekeeper` folder (create it if it doesn't exist)
2. Add: `ADMIN_PASSWORD=yournewpassword`
3. Restart the app:
   ```bash
   docker compose up -d app
   ```
4. Log in with the new password
5. Remove the `ADMIN_PASSWORD` line from `.env` and restart again (so the password is stored securely, not in a file)

**Option 2 — Reset via the database directly:**

```bash
docker compose exec db psql -U gatekeeper gatekeeper \
  -c "UPDATE settings SET value = NULL WHERE key = 'admin_password_hash';"
docker compose restart app
```

Then visit `http://localhost` — you'll be taken back to the setup wizard to set a new password.

---

## Troubleshooting

### "Cannot connect" or blank page at http://localhost

1. Make sure Docker Desktop is open and running (look for the whale icon in your menu bar / system tray)
2. Check that the containers are running: `docker compose ps`
3. Check the app logs: `docker compose logs app --tail=30`

### Port 80 already in use

If another application is using port 80, Gatekeeper's nginx can't start. You'll see an error like `Bind for 0.0.0.0:80 failed`.

**Fix:** Edit `docker-compose.yml` and change the nginx port mapping from `"80:80"` to `"8080:80"`, then access Gatekeeper at `http://localhost:8080`.

### "Docker daemon not running"

Docker Desktop is not started. Open Docker Desktop and wait for it to finish loading before running `docker compose up`.

### Containers keep restarting

Check logs for the failing service:

```bash
docker compose logs app --tail=50
docker compose logs db --tail=50
```

Common causes: database migration failed, out of disk space, or a port conflict.

### Starting fresh (wipe all data)

> **Warning:** This permanently deletes all your trades, ideas, and journal entries.

```bash
docker compose down -v
docker compose up -d
```

The `-v` flag removes the Docker volumes (your data). The app will start fresh and redirect you to setup.

---

## AI Setup (optional)

AI features (Plan Builder, Idea Review, Journal Coach) require an API key from an AI provider. This is optional — Gatekeeper works fully without it.

Go to **Settings** after logging in and configure your provider:

| Provider | What you need |
|---|---|
| Anthropic (Claude) | API key from [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | API key from [platform.openai.com](https://platform.openai.com) |
| Ollama (local, free) | Ollama running locally at `http://localhost:11434` |

API keys are stored in your local database — they never leave your machine.

You can also set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in a `.env` file in the gatekeeper folder as an alternative to entering them in Settings.

---

## Development

```bash
# Install dependencies
uv sync

# Run tests (requires Docker for Postgres)
docker compose -f tests/docker-compose.test.yml up -d
SKIP_SECURITY_CHECKS=1 uv run pytest

# Check coverage
SKIP_SECURITY_CHECKS=1 uv run pytest --cov=app/services --cov-report=term-missing

# Run locally without Docker
export DATABASE_URL=postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper
export SKIP_SECURITY_CHECKS=1
uv run uvicorn app.main:app --reload
```

Tests use a throwaway Postgres container on port 5433. Each test gets a fresh schema, so they are fully isolated.

See [CLAUDE.md](CLAUDE.md) for architecture rules, code conventions, and the development workflow.

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

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

[AGPL-3.0](LICENSE)
