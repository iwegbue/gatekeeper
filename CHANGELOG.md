# Changelog

All notable changes to Gatekeeper Core are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Multiple Trading Plans** — create, duplicate, and switch between multiple trading plans; only one plan is active at a time and new ideas use the active plan; existing ideas keep the plan they were created with
  - Plan list page at `/plan` with activate, duplicate, and delete actions
  - Plan detail page at `/plan/{id}` with full rule management
  - Rule edit and delete URLs scoped to plan: `/plan/{id}/rules/{rule_id}/edit` and `/plan/{id}/rules/{rule_id}/delete`
  - New plan creation at `/plan/new` with optional template pre-fill
  - Plan duplication copies all rules (including inactive) to a new inactive plan
  - Plan deletion blocked if the plan is currently active or has ideas attached
  - API endpoints: `GET/POST /api/v1/plans`, `GET/PATCH/DELETE /api/v1/plans/{id}`, `POST /api/v1/plans/{id}/activate`, `POST /api/v1/plans/{id}/duplicate`
  - Backward-compatible `/api/v1/plan` endpoints still work (operate on the active plan)
  - Ideas now store `plan_id` to track which plan they were created under
  - Migration `008_multiple_trading_plans` with backfill for existing data
  - 17 new tests in `test_multi_plan.py`

- **Plan Builder UX overhaul** — strategy archetype suggestion chips (breakouts, pullbacks, mean reversion, momentum, range, supply & demand) with timeframe and market selectors so new users can start without a blank page; AI responses now render as formatted HTML (markdown via marked.js); animated thinking indicator while the AI responds; user and AI messages are visually distinct with avatars and differentiated bubble styles; after completing the builder, redirects to the active plan's detail page (`/plan/{id}`) rather than the plan list

- **Settings / AI** — `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` env vars (e.g. Docker `.env`) are now seeded into the database on first boot, identical to entering them via the UI; `OPENAI_API_KEY` is also wired into `app/config.py` and `docker-compose.yml` for parity with Anthropic
- **Reset Plan** — new `/plan/{id}/reset` page lets you wipe all existing rules and optionally load a starter template (Trend Following, Mean Reversion) or start from scratch; plan name and description can be updated at the same time

- **Plan Validation Engine (Phase 1 — Interpretability)** — AI-assisted compilation of trading plan rules into machine-testable proxies
  - `POST /api/v1/validation/compile` — compile the active plan; each rule is mapped to a proxy from a fixed vocabulary (16 proxy types across all 7 layers) using the configured AI provider; BEHAVIORAL rules auto-classified as NOT_TESTABLE without an AI call
  - `GET /api/v1/validation/runs` — list past validation runs
  - `GET /api/v1/validation/runs/{id}` — get run detail with compiled plan and feedback report
  - `PUT /api/v1/validation/compiled-plans/{id}/rules/{rule_id}/confirm` — user reviews and can override AI-proposed interpretations
  - HTML routes at `/validation` (history) and `/validation/runs/{id}` (report) with "Validate Plan" sidebar link
  - Interpretability score (% of non-behavioral rules that are testable or approximated)
  - Deterministic coherence checks: gap detection, underfiltering/overfiltering warnings, redundancy detection
  - Structured feedback report with per-layer rule breakdowns, replay readiness assessment (`READY / PARTIAL / NOT_READY`), and actionable refinement suggestions
  - `CompiledPlan` and `ValidationRun` models; migration `006_add_validation_tables`
  - 58 new tests across `test_rule_interpreter`, `test_plan_compiler`, `test_feedback_service`, `test_validation_api`

- **MCP server** — Gatekeeper is now an MCP server, mountable at `/mcp` (StreamableHTTP transport)
  - 16 tools covering the full workflow: `create_idea`, `get_idea`, `list_ideas`, `toggle_check`, `advance_idea`, `regress_idea`, `invalidate_idea`, `open_trade`, `close_trade`, `update_stop_loss`, `take_partial`, `lock_breakeven`, `list_trades`, `get_trade`, `list_journal`, `get_journal_entry`, `update_journal_entry`, `complete_journal_entry`, `review_idea`, `coach_journal`, `get_status`
  - 4 resources for agent context: `gatekeeper://plan`, `gatekeeper://ideas/active`, `gatekeeper://trades/open`, `gatekeeper://discipline`
  - State machine guards enforced — agents cannot skip layers; errors are surfaced as tool error responses
  - MCP lifespan combined with app lifespan; mounted via `fastmcp` at `/mcp`
  - 14 new tests in `test_mcp_tools.py`

- **`gk` CLI** — command-line interface for scripting, automation, and MCP stdio transport
  - `gk status` — health, version, active counts
  - `gk ideas list/show/create/advance/regress/invalidate/check`
  - `gk trades list/show/open/close/update-sl/partial/be`
  - `gk journal list/show/edit/complete`
  - `gk plan show`
  - `gk report discipline`
  - `gk ai review/coach`
  - `gk mcp [--transport stdio|sse] [--port N]` — launch MCP server for Claude Desktop / Cursor
  - `gk config set/show` — persist URL and token to `~/.config/gatekeeper/config.toml`
  - All commands support `--json` for machine-readable output and `--url`/`--token` overrides
  - Registered as `gk` entry point in `pyproject.toml`

- **Help section** — comprehensive in-app help and guide at `/help` covering the full workflow, 7-layer system, idea states, rules & checklist, trades, grading, journal, reports, AI features, and API/CLI; accessible from sidebar and top bar; includes sticky table-of-contents with scroll-tracking, responsive layout, and state flow diagram

- **SMTP email notifications** — replaced SendGrid with standard SMTP (Python `smtplib`); works with Gmail, Proton Mail Bridge, Mailhog, self-hosted Postfix, and any SMTP relay; configurable from Settings UI
- **Telegram notifications** — bot token and chat ID now stored in DB and configurable from the UI instead of environment variables only
- **Notifications settings card** — new collapsible "Notifications" card in Settings with SMTP config, Telegram config, per-channel enable toggles, and one-click test-send buttons for both channels
- **`notifications_enabled` flag now enforced** — master toggle and per-channel toggles are respected before sending; previously the flag was stored but never read
- **Trade-close notifications** — `notify_trade_closed` is now wired to `trade_service.close_trade()` (was dead code); fires email and/or Telegram with instrument, direction, and R-multiple
- **Migration `005_notification_settings`** — adds 11 new columns to the `settings` table for SMTP host/port/credentials and Telegram bot token/chat ID

- **Setup walkthrough wizard** — 5-step onboarding flow after initial password setup: Welcome intro, AI provider configuration, trading plan selection, watchlist builder, and quick tour
- **Plan starter templates** — two curated rule sets (Trend Following, Mean Reversion) covering all 7 layers to help new users get started immediately; fully editable after setup
- **`setup_completed` flag** — new `settings.setup_completed` boolean column (migration `004_add_setup_completed`) tracks whether onboarding has been completed; authenticated users are redirected to the wizard until it is

---

## [0.2.0] — 2026-03-21

### Added

- **JSON API layer** (`/api/v1/`) — ~30 endpoints covering ideas, trades, journal, plan, instruments, reports, and AI; bearer token auth
- **API token management** — generate/regenerate token from Settings UI; SHA-256 hash stored in DB; migration `002_add_api_token_hash`
- **`CLAUDE.md`** — AI assistant instructions, architecture rules, and dev workflow spec
- **`SKIP_SECURITY_CHECKS`** env var — allows bypassing startup guards in dev/test

### Security

- Startup guard: refuses to start with default `SECRET_KEY` or `ADMIN_PASSWORD`
- CSRF protection on all HTML POST routes (17 endpoints) using itsdangerous
- Rate limiting (slowapi): 5 req/min per IP on `/login` and `/api/v1/auth/token`
- Security headers on every response: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS
- Timing-safe password comparison (`hmac.compare_digest`) on token endpoint
- SSRF prevention: `ollama_base_url` validated against localhost allowlist
- API key masking in settings template — never rendered as plaintext `value=`
- Session cookie upgraded to `SameSite=strict`
- `docker-compose.yml`: `SECRET_KEY` and `ADMIN_PASSWORD` now required (`:?` syntax)

### Fixed

- **Plan validation / rule interpreter**: parse model replies wrapped in markdown JSON code fences, leading prose, or trailing text; treat empty or missing content with a clear user-facing message instead of raw JSON parse errors (e.g. “Expecting value: line 1 column 1”)
- **OpenAI provider**: coerce `message.content` `None` to `""` so downstream parsing does not mis-handle refusals or empty completions
- `plan_service.update_rule`: protect `id`, `plan_id`, `layer`, `created_at` from mutation
- `ChecklistItemResponse` schema: add `ConfigDict(from_attributes=True)`
- `PATCH /api/v1/journal/{id}`: guard against `None` after tag re-fetch
- `plan_builder` router: log full exception server-side, return generic message to client
- Narrow `except Exception` in session token verification to `BadSignature`/`SignatureExpired`

---

## [0.1.0] — 2026-03-21

Initial release.

### Added

- **7-layer trading plan** — CONTEXT, SETUP, CONFIRMATION, ENTRY, RISK, MANAGEMENT, BEHAVIORAL
- **Layer-gated state machine** — WATCHING → SETUP_VALID → CONFIRMED → ENTRY_PERMITTED → IN_TRADE → MANAGED → CLOSED; INVALIDATED from any non-terminal state
- **Weighted checklist grading** — A (≥85%), B (65–84%), C (<65%); advisory rules visible but non-blocking
- **Trade management** — open from ENTRY_PERMITTED, partial/BE management, R-multiple on close
- **Auto-journal** — draft created on trade close with plan adherence % and rule violations
- **Plan Builder** — multi-turn wizard (BYOK: Anthropic, OpenAI, Ollama)
- **AI idea review** — checklist analysis against plan
- **AI journal coach** — behavioral pattern identification
- **AI rule clarity check** — push vague rules toward precision
- **Discipline reports** — discipline score, adherence trend, grade distribution, violation frequency
- **Background tasks** — entry window expiry invalidation
- **HTMX frontend** — responsive, server-rendered, Pico CSS
- **Test suite** — 174 tests, 88% service coverage, real Postgres in CI
