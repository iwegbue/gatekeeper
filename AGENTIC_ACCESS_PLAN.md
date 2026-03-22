# Agentic Access Plan for Gatekeeper Core

## Context

The open-source community is trending towards exposing agentic interfaces
(MCP servers, JSON APIs, CLI tools) that allow AI agents and automation
pipelines to interact with developer and productivity tools. Gatekeeper Core
is well-positioned for this — the service layer is already decoupled from
HTTP routing, and the domain has well-bounded, named operations with explicit
guards (the state machine).

This plan covers three layers of agentic access, each building on the last.

---

## Phase 1: JSON API Layer (`/api/v1`)

**Goal:** Add a parallel set of JSON endpoints alongside the existing HTML routes.
No refactoring of services needed — just new routers that call the same service
functions and return Pydantic response models.

### Auth

Single bearer token, stored hashed in the `settings` table. Generated from
the Settings page or via a CLI command. Checked via a FastAPI dependency
(`Depends(verify_api_token)`).

```
Authorization: Bearer gk_xxxxxxxxxxxxxxxxxxxx
```

### Endpoints

#### Read Operations

```
GET  /api/v1/plan                      → Plan + all rules by layer
GET  /api/v1/plan/rules                → Flat list of rules (filterable by layer, type)
GET  /api/v1/ideas                     → List ideas (filter: state, instrument, grade)
GET  /api/v1/ideas/{id}                → Idea detail + checklist + grade
GET  /api/v1/ideas/{id}/checklist      → Checklist items with completion state
GET  /api/v1/trades                    → List trades (filter: open/closed)
GET  /api/v1/trades/{id}               → Trade detail + linked journal
GET  /api/v1/journal                   → List journal entries
GET  /api/v1/journal/{id}              → Journal entry detail
GET  /api/v1/instruments               → List instruments
GET  /api/v1/reports/discipline        → Discipline summary (stats, grade dist, adherence)
GET  /api/v1/status                    → App health + version + active ideas/trades count
```

#### Write Operations

```
POST /api/v1/ideas                     → Create idea (instrument, direction, notes)
POST /api/v1/ideas/{id}/checks/{cid}   → Toggle rule check
POST /api/v1/ideas/{id}/advance        → Advance state (guards enforced)
POST /api/v1/ideas/{id}/regress        → Regress state
POST /api/v1/ideas/{id}/invalidate     → Invalidate idea

POST /api/v1/trades                    → Open trade from idea
POST /api/v1/trades/{id}/update-sl     → Update stop loss
POST /api/v1/trades/{id}/partial       → Take partial
POST /api/v1/trades/{id}/be            → Lock breakeven
POST /api/v1/trades/{id}/close         → Close trade

POST /api/v1/journal/{id}              → Update journal entry fields
POST /api/v1/journal/{id}/complete     → Mark entry complete
```

#### AI Trigger Operations

```
POST /api/v1/ai/idea-review/{id}      → Run AI review on idea
POST /api/v1/ai/journal-coach/{id}    → Run AI coach on journal entry
POST /api/v1/ai/rule-clarity          → Refine a rule description
```

### Implementation Notes

- New directory: `app/routers/api/v1/` with one file per resource
- Pydantic response schemas in `app/schemas/` (or inline)
- Shared dependency for token auth: `app/auth.py` gets `verify_api_token()`
- All existing guards, validations, and state machine rules apply identically
- Error responses use standard HTTP codes + JSON error body

### Estimated Scope

~10-12 new router files, ~15 Pydantic schemas, 1 auth dependency, 1 migration
(add `api_token_hash` column to settings or a new `api_tokens` table).

---

## Phase 2: MCP Server

**Goal:** Expose Gatekeeper operations as an MCP (Model Context Protocol) server
so that Claude, Cursor, Windsurf, and other MCP-compatible agents can interact
with a trader's Gatekeeper instance natively.

### Architecture

Two options:

**Option A — Embedded MCP (recommended for simplicity)**
Add an MCP endpoint directly inside the FastAPI app using the MCP Python SDK.
The MCP server calls the same service layer. Runs as an SSE transport on
`/mcp` or as a stdio transport launched separately.

**Option B — Standalone MCP binary**
A separate lightweight Python process that connects to Gatekeeper's JSON API
(Phase 1). More decoupled but adds a network hop and token management.

### MCP Tools (maps to Phase 1 endpoints)

```
Tools:
  get_plan              → Read trading plan and rules
  list_ideas            → List ideas with optional state filter
  get_idea              → Get idea detail with checklist and grade
  toggle_check          → Toggle a rule check on an idea
  advance_idea          → Advance idea state
  regress_idea          → Regress idea state
  invalidate_idea       → Invalidate idea
  create_idea           → Create new idea
  list_trades           → List trades (open/closed)
  get_trade             → Trade detail
  open_trade            → Open trade from idea
  close_trade           → Close trade with exit price
  update_stop_loss      → Modify SL on open trade
  take_partial          → Partial close
  lock_breakeven        → Lock BE
  get_discipline_report → Discipline stats and trends
  list_journal          → List journal entries
  get_journal_entry     → Journal entry detail
  review_idea           → Trigger AI idea review
  coach_journal         → Trigger AI journal coaching

Resources:
  gatekeeper://plan            → Current trading plan (read-only context)
  gatekeeper://ideas/active    → Active ideas summary
  gatekeeper://trades/open     → Open trades summary
  gatekeeper://discipline      → Latest discipline snapshot
```

### Why MCP fits Gatekeeper

- **Bounded operations** — each tool is a single, well-named action
- **State machine guards** — agents can't skip layers; the server enforces discipline
- **Read-heavy context** — agents need plan rules and idea state as context before acting
- **Human-in-the-loop natural fit** — MCP clients surface tool calls for user approval

---

## Phase 3: `gatekeeper-cli` — Self-Hosted Agentic Toolkit

**Goal:** A CLI tool that ships with gatekeeper, allowing users who run
Gatekeeper on their own VPS to install agent capabilities locally.

### Why a CLI?

Users running Gatekeeper on a VPS already have SSH access. A CLI tool:

1. **Avoids exposing the API publicly** — CLI talks to localhost or Unix socket
2. **Enables cron/systemd automation** — schedule checks, market scans, journaling reminders
3. **Pairs with the Bridge Worker pattern** — like how bridge_worker is a sidecar process
   for MT5, the CLI can be a sidecar for agentic workflows
4. **Composable with shell pipelines** — `gk ideas --active --json | jq ...`
5. **Entry point for MCP stdio transport** — `gk mcp` launches the MCP server
   over stdio, which Claude Desktop / Cursor can connect to directly

### Design

```
gk <resource> <action> [options]
```

#### Core Commands

```bash
# Plan
gk plan show                          # Display plan with rules by layer
gk plan rules --layer SETUP           # Filter rules by layer

# Ideas
gk ideas list                         # List ideas (default: active only)
gk ideas list --all --json            # All ideas, JSON output
gk ideas show <id>                    # Idea detail with checklist
gk ideas create --instrument GBPUSD --direction LONG --notes "..."
gk ideas check <idea_id> <check_id>   # Toggle a rule check
gk ideas advance <id>                 # Advance state
gk ideas regress <id>                 # Regress state
gk ideas invalidate <id>             # Invalidate

# Trades
gk trades list                        # Open trades
gk trades list --closed               # Closed trades
gk trades show <id>                   # Trade detail
gk trades open <idea_id> --entry 1.2650 --sl 1.2600 --size 0.5
gk trades close <id> --exit 1.2700
gk trades update-sl <id> --sl 1.2620
gk trades partial <id> --fraction 0.5 --exit 1.2680
gk trades be <id>

# Journal
gk journal list
gk journal show <id>
gk journal edit <id> --what-went-well "..." --lessons "..."
gk journal complete <id>

# Reports
gk report discipline                  # Summary stats
gk report discipline --json           # Machine-readable

# AI
gk ai review <idea_id>               # AI idea review
gk ai coach <journal_id>             # AI journal coaching

# MCP Server
gk mcp                               # Launch MCP stdio server
gk mcp --transport sse --port 3001   # Launch MCP SSE server

# Status
gk status                            # Health, version, counts
```

#### Global Flags

```
--url <base_url>         # Default: http://localhost:8000
--token <api_token>      # Or GK_API_TOKEN env var
--json                   # JSON output (default is human-readable table)
--quiet                  # Minimal output (for scripting)
```

### Implementation

- **Language:** Python (same ecosystem, shares Pydantic schemas with core)
- **HTTP client:** `httpx` (already a dependency)
- **CLI framework:** `click` or `typer` (Typer preferred — builds on Pydantic)
- **Distribution:** Ships inside the gatekeeper repo as `gk` entry point
  in `pyproject.toml`, or installable standalone via `pip install gatekeeper-cli`
- **Config file:** `~/.config/gatekeeper/config.toml` for URL + token persistence

### Agentic Automation Examples

```bash
# Cron: Every morning at 7am, review all active ideas
gk ideas list --state WATCHING --json | \
  jq -r '.[].id' | \
  xargs -I{} gk ai review {}

# Systemd timer: Nightly discipline check
gk report discipline --json | \
  jq '.discipline_score' | \
  xargs -I{} test {} -lt 70 && \
  gk notify "Discipline score below 70 — review your journal"

# Claude Desktop MCP integration
# In claude_desktop_config.json:
{
  "mcpServers": {
    "gatekeeper": {
      "command": "gk",
      "args": ["mcp"],
      "env": {
        "GK_API_URL": "http://localhost:8000",
        "GK_API_TOKEN": "gk_xxxxxxxxxxxx"
      }
    }
  }
}
```

---

## Bridge Worker Observations

The existing **bridge_worker** (in private gatekeeper repo) validates this
entire pattern:

| Aspect | Bridge Worker | gatekeeper-cli |
|--------|--------------|----------------|
| Role | Sidecar for MT5 execution | Sidecar for agentic access |
| Comms | Direct DB (shared PostgreSQL) | HTTP API (Phase 1 endpoints) |
| Runs on | Windows (where MT5 lives) | Any machine (VPS, local) |
| Trigger | LISTEN/NOTIFY + polling | CLI invocation + cron + MCP |
| State | Stateless between cycles | Stateless per invocation |

The bridge worker proves that Gatekeeper's architecture supports sidecar
processes well. The CLI follows the same philosophy — a lightweight process
that extends Gatekeeper without modifying the core.

**Key difference:** Bridge Worker uses direct DB access (it lives on the same
host and needs sub-second latency for trading). The CLI should use the HTTP API
instead — it's safer, doesn't couple to the schema, and works across networks.

---

## Sequencing

```
Phase 1 (JSON API)     ████████░░░░░░░░  ~2 weeks
Phase 2 (MCP Server)   ░░░░░░░░████░░░░  ~1 week (builds on Phase 1)
Phase 3 (CLI)          ░░░░░░░░░░░░████  ~1 week (HTTP client for Phase 1)
```

Phase 1 is the foundation — both MCP and CLI consume it. Phase 2 and 3 can
be developed in parallel once Phase 1 is stable.

---

## Open Questions

1. **API token scope** — Single admin token, or support multiple tokens with
   read-only vs read-write permissions?
2. **Rate limiting** — Needed for a single-user app? Probably not initially,
   but worth considering if MCP agents get chatty.
3. **Webhook support** — Should the API support outbound webhooks (trade closed,
   idea advanced) in addition to polling? Would enable event-driven agents.
4. **CLI packaging** — Ship as part of the Docker image, or separate `pip install`?
   Docker users might want `docker exec gk-app gk ideas list`.
5. **MCP transport** — stdio (simpler, for local use) vs SSE (for remote)?
   Probably support both.
