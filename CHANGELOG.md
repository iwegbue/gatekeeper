# Changelog

All notable changes to Gatekeeper Core are documented here.

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
