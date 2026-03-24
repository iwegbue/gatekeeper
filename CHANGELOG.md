# Changelog

All notable changes to Gatekeeper Core are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **README overhaul** — rewritten for traders, not developers
  - Honest prerequisites section: Docker Desktop (~700MB), Git, and a terminal — with links and plain-language descriptions
  - ZIP download alternative to `git clone` for users without Git
  - **Daily use** section: how to start and stop Gatekeeper each day
  - **Updating Gatekeeper** section: step-by-step update instructions with explanation of what each command does
  - **Backing up your data** section: `pg_dump` one-liner + restore instructions
  - **Forgotten password** section: two recovery paths (env var override and direct DB reset)
  - **Troubleshooting** section: "cannot connect", port 80 conflict, Docker not running, containers restarting, starting fresh
  - AI setup section rewritten with plain-language provider descriptions and direct links to API key consoles
  - Tech stack and architecture sections moved to the bottom (relevant to contributors, not traders)
  - State machine workflow updated to use display labels (Watching → Context & Setup Valid → Confirmed → Entry Permitted → In Trade → Managed → Closed)

- **UX audit & beginner-friendliness improvements** — comprehensive UX review for traders at all levels; principle of progressive clarity: self-evident on first encounter, full depth available on demand
  - `docs/UX_SPEC.md` — canonical design spec: audience, voice & tone, terminology glossary, state display name mapping, grading reference, abbreviation rules, tooltip standards, progressive disclosure patterns, error message standards
  - `CLAUDE.md` — new "UX & Language Guidelines" section: audience statement, terminology rules, abbreviation intro rules, state label mapping, tooltip standards, action button rules, progressive disclosure rules, error message rules
  - `app/templates/_macros/states.html` — new Jinja2 macro mapping `IdeaState` enum values to human-readable display labels; import with `{% from "_macros/states.html" import state_label %}`
  - **State display labels** across all templates: `WATCHING` → "Watching", `SETUP_VALID` → "Context & Setup Valid", `CONFIRMED` → "Confirmed", `ENTRY_PERMITTED` → "Entry Permitted", `IN_TRADE` → "In Trade", `MANAGED` → "Managed", `CLOSED` → "Closed", `INVALIDATED` → "Invalidated" — raw enum values retained only in API/CLI documentation
  - **Help page glossary** — new Glossary section at the top of `/help` with definitions for all UI terms (Idea, Layer, Rule, R-multiple, SL, TP, BE, Partials, Discipline Score, Plan Adherence, Entry Window, Violation, etc.)
  - **Help page: grading thresholds table** — A = 85%+, B = 65–84%, C = below 65% shown explicitly in the Grading section
  - **Help page: state display labels** in the state machine diagram and gate-requirements table; enum values noted in collapsed API/CLI note
  - **Dashboard: sequential first-use guide** — replaces 4-link list with a numbered step-by-step flow (Set up plan → Add instruments → Create first idea); AI configuration moved to optional note
  - **Dashboard: KPI help links** — "?" links on Discipline Score and Avg R cards linking to `/help#discipline-score` and `/help#grading`
  - **Grade/score transparency** — checklist score now shows percentage explicitly (e.g. "42/67 pts (63%)"); grade legend "A = 85%+ · B = 65–84% · C = below 65%" shown below the progress bar
  - **Corrected grade thresholds** in dashboard tooltips (were showing 80%/60%, now correctly show 85%/65%)
  - **Plan Builder prominence** — on empty plan state, Plan Builder is primary CTA with "Recommended" note; starter templates (Trend Following, Mean Reversion) surfaced as cards on plan index page (not just in setup wizard); "Load a starter template" cards link to reset page with template pre-selected
  - **Help link** moved up into the Analysis sidebar group (alongside Reports), making it more discoverable
  - **Abbreviation `<abbr>` tags** — SL, TP, BE, and R introduced with full-form tooltips on first appearance per page (trades/detail, dashboard)

### Changed

  - `app/routers/plan.py`: `plan_reset_confirm` now accepts optional `preselect` query param and passes it to the reset template for template pre-selection
  - `app/templates/plan/reset.html`: JS `selectTemplate()` now initialises from the `preselect` template variable instead of hardcoded `'scratch'`
  - **Entry window** — label upgraded with tooltip explaining what it is, when to set it, and what happens when it expires
  - **Invalidate vs Delete** — both danger-zone cards now include a brief plain-language description below the header explaining when to use each action
  - **Partials / BE locked** — display labels updated ("Partial Exits", "Breakeven Locked"); management buttons renamed ("Take Partial Exit", "Lock Breakeven") with improved title attributes
  - **R-multiple** — labelled with `<abbr>` tag for first-time users; tooltip improved
  - **Discipline Score tooltip** — updated with explicit formula: plan adherence + grade distribution + violation rate; includes "Aim for 70+"
  - **Rule type tooltips** — OPTIONAL and ADVISORY tooltips now explicitly distinguish their difference (OPTIONAL improves grade; ADVISORY has no effect on grade or advancement)
  - **Weight tooltip** — updated to guide rule authors: 1 = nice-to-have, 2 = important, 3 = critical non-negotiables not already Required
  - **Plan adherence tooltip** on trades/detail — updated with explicit definition and aim
  - **State tooltip** on ideas dashboard — updated from "REQUIRED" jargon to plain language



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

- **Plan Validation Engine (Phase 1 — Interpretability)** — AI-assisted classification of trading plan rules by data-source requirements
  - `POST /api/v1/validation/compile` — compile the active plan; each rule is classified as `OHLC_COMPUTABLE`, `OHLC_APPROXIMATE`, or `LIVE_ONLY` based on whether it can be evaluated from OHLC price data; BEHAVIORAL rules auto-classified as `LIVE_ONLY` without an AI call
  - `GET /api/v1/validation/runs` — list past validation runs
  - `GET /api/v1/validation/runs/{id}` — get run detail with compiled plan and feedback report
  - `PUT /api/v1/validation/compiled-plans/{id}/rules/{rule_id}/confirm` — user reviews and can override AI-proposed classifications; override accepts `status` and `data_sources_required`
  - HTML routes at `/validation` (history) and `/validation/runs/{id}` (report) with "Validate Plan" button on plan detail page
  - Interpretability score (% of non-behavioral rules that are OHLC_COMPUTABLE or OHLC_APPROXIMATE)
  - Deterministic coherence checks: gap detection, underfiltering/overfiltering warnings, missing entry/risk rule warnings
  - Structured feedback report with per-layer rule breakdowns, replay readiness assessment (`READY / PARTIAL / NOT_READY`), and actionable refinement suggestions
  - `CompiledPlan` and `ValidationRun` models; migration `006_add_validation_tables`
  - 58 new tests across `test_rule_interpreter`, `test_plan_compiler`, `test_feedback_service`, `test_validation_api`

- **Plan Review** — AI-powered analysis of your trading plan based on a sample of real trades and journal entries
  - Available once you have reached the configured sample size of completed, journaled trades (default: 20)
  - Triggered from the plan detail page at `/plan/{id}/review`; results stored as `PlanReview` records
  - Report covers: overall verdict (keep / refine / overhaul), per-rule performance (adherence %, win rate when followed vs. skipped), assumptions held/challenged, and suggested plan changes
  - `GET /api/v1/plans/{id}/review/runs` — list reviews; `GET /api/v1/plans/{id}/review/runs/{review_id}` — detail; `POST /api/v1/plans/{id}/review/run` — trigger
  - Sample size configurable in Settings → General → Plan Review Sample Size (min 5)
  - `PlanReview` model; migrations `009_add_plan_review_sample_size`, `010_add_plan_reviews_table`

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

### Changed

- **Plan Validation — Phase 1 redesign** — rule classification no longer uses a fixed proxy vocabulary; the AI now answers one question: "Can this rule be evaluated from OHLC data?" Status values changed from `TESTABLE / APPROXIMATED / NOT_TESTABLE` to `OHLC_COMPUTABLE / OHLC_APPROXIMATE / LIVE_ONLY`; compiled rules now carry `data_sources_required` (free-form list of OHLC data streams) instead of `proxy` + `feature_dependencies`; old status values remain as legacy aliases for stored data backward-compatibility; proxy-based redundancy coherence check removed from Phase 1 (belongs in Phase 2)

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
