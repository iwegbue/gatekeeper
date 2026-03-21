# Changelog

All notable changes to Gatekeeper Core are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

_Changes staged for the next release._

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
- **AI plan builder** — multi-turn wizard (BYOK: Anthropic, OpenAI, Ollama)
- **AI idea review** — checklist analysis against plan
- **AI journal coach** — behavioral pattern identification
- **AI rule clarity check** — push vague rules toward precision
- **Discipline reports** — discipline score, adherence trend, grade distribution, violation frequency
- **Background tasks** — entry window expiry invalidation
- **HTMX frontend** — responsive, server-rendered, Pico CSS
- **Test suite** — 174 tests, 88% service coverage, real Postgres in CI
