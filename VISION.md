# Vision — Gatekeeper Core

## What Gatekeeper Is

Gatekeeper is a rule-enforced trading system.

You define your trading rules. Gatekeeper enforces them before you can take a trade.
Over time, it shows you which rules actually work — and keeps you accountable to them.

That's it. Everything else follows from this.

**Gatekeeper Core** is the open-source foundation: plan definition, state machine enforcement, journaling, reporting, and agentic access (API/MCP/CLI). **Gatekeeper Pro** is a commercial tier built on Core that adds broker bridge execution, auto-trade mode, and managed hosting.

---

## Why This Exists

Traders don't fail because they lack strategy. They fail because they break their own rules.

They skip confirmations when they're impatient. They size up after a win streak. They move stops when they're scared. The edge was there — they just didn't follow it.

The usual answer is "be more disciplined." That's not a system. That's a wish.

Gatekeeper replaces willpower with structure. Your rules become gates. Inside the system, you cannot advance an idea or open a trade until every required rule is satisfied. Outside it, nothing stops you from opening your broker directly — that's a human choice. The goal of Core is to make breaking your rules a deliberate act, not a reflexive one. Gatekeeper Pro closes that gap further by connecting enforcement to execution via the broker bridge.

**Humans break their own rules. Systems don't.**

---

## The Core Loop

```
Define rules → Enforce rules → Measure rules → Refine rules
```

Everything in Gatekeeper serves this loop:

| Phase | What Gatekeeper does |
|-------|---------------------|
| **Define** | 7-layer plan structure. Multiple plans (one active at a time). AI-assisted plan builder. Starter templates. |
| **Enforce** | Layer-gated state machine. You cannot open a trade until every required rule is satisfied. |
| **Measure** | Auto-journal on close. Plan adherence %. Discipline score. Grade distribution. Violation tracking. |
| **Refine** | AI journal coaching. Rule clarity checks. Plan validation (rule → testable proxy compilation). |

The loop tightens over time. Vague rules get sharpened. Rules that don't contribute get exposed. The plan evolves from intuition into a tested, enforceable system.

---

## Design Principles

**1. Enforcement over advice.**
Gatekeeper doesn't suggest you follow your plan. The state machine gates every step — you cannot advance an idea until its layer's rules are satisfied. This is structural friction, not a hard lock: nothing prevents a trader from opening their broker directly and bypassing the system entirely. Core's job is to make that bypass a deliberate, conscious choice rather than a reflexive one. Gatekeeper Pro narrows this gap further by connecting rule state to broker execution — the bridge can block or place orders based on whether rules are satisfied, making enforcement real at the execution layer.

**2. The trader stays in control.**
Gatekeeper enforces *your* rules, not its own. You define what matters. You set the weights. You decide what's required vs. advisory. The system is opinionated about *process*, never about *strategy*.

**3. Self-hosted first.**
One instance per trader. Your data stays on your machine. Self-hosted is the default and the primary deployment model. A hosted option may exist in the future for convenience, but the core product always works without depending on external infrastructure.

**4. Reveal depth progressively.**
The entry point is simple: "define rules, enforce rules." AI, backtesting, automation, agentic access — these are discovered later, not pitched upfront. The product earns complexity.

**5. Bring your own everything.**
AI provider, broker connection, hosting — Gatekeeper integrates with what you already use. No vendor lock-in. BYOK is the default, not an option.

**6. Measure what matters.**
Discipline score, not P&L. Plan adherence, not win rate. Gatekeeper tracks whether you followed *your* process — the only variable you actually control.

**7. Work with agents, not just humans.**
The JSON API, MCP server, and CLI exist so that AI agents and automation can interact with Gatekeeper using the same rules and guards as the human trader. Agents don't get shortcuts.

---

## Category

Gatekeeper is a **rule-enforced trading system**.

It is not:
- A trading journal (journaling is one output of enforcement, not the product)
- A signal service (it enforces *your* rules — it doesn't generate trade ideas for you)
- An AI trading assistant (AI assists plan-building and review — it doesn't make trading decisions)
- A backtesting platform (validation is a tool for refining rules, not the core offering)

Gatekeeper Core gates *permission* to trade. The Pro tier extends enforcement into execution via the broker bridge — auto-trade mode can place and manage orders when rules are satisfied — but the core product's job is ensuring rules are followed, not replacing the trader.

---

## Roadmap

### Now — Ship v0.3.0, then deepen the loop

The foundation is solid. The immediate priority is releasing the substantial body of work currently in Unreleased as **v0.3.0**:

- MCP server (StreamableHTTP transport, 21 tools, 4 resources)
- `gk` CLI (full workflow coverage, stdio MCP transport)
- Plan Validation Engine Phase 1 — rule interpretability, testable proxy compilation, coherence checks
- Setup wizard and plan starter templates
- SMTP + Telegram notifications
- Help section
- Plan reset with template loading
- Multiple trading plans (plan list, plan detail, plan-scoped rules, delete guard)

Once v0.3.0 is shipped, the next focus areas are:

- **Plan Validation Phase 2 — Replay.** Run compiled rules against historical price data to measure how they would have filtered. Move from "are your rules testable?" to "do your rules actually filter well?"
- **Notification expansion.** More trigger points beyond trade-close (idea invalidated, discipline score drop, entry window expiry). Webhook support for event-driven automation.
- **Rule performance attribution.** Per-rule statistics: how often is each rule the blocking gate? Which rules correlate with better outcomes? Surface this in reports so traders can prune and sharpen.

### Next — Closing the feedback loop

- **Outcome tagging.** Link trade results back to specific rule states at entry. "When you skipped rule X, your average R was -0.8. When you followed it, +1.4."
- **Plan versioning.** Track plan changes over time. Compare discipline and outcomes across plan versions. Know whether your refinements are actually improving the system.
- **Equity and drawdown tracking.** R-multiple equity curve, drawdown periods, recovery time. Not as a P&L tracker — as evidence of whether the *system* is working.
- **Multi-instrument correlation awareness.** Warn when multiple open ideas share correlated exposure. A rule-enforcement system should enforce portfolio-level rules too.

### Later — Expanding the enforcement boundary

- **Broker bridge integrations.** Beyond the existing MT5 bridge — adapters for cTrader, IBKR, and webhook-based brokers. Gatekeeper gates permission; the bridge executes.
- **Automated rule detection.** The system observes market conditions and checks rules without manual toggling. The trader still approves — but the checklist fills itself where possible.
- **Community plan templates.** Curated, peer-reviewed rule sets for common strategies. Not signals — *structures*. A starting point that traders customize and own.
- **Mobile / PWA access.** Responsive UI already works on mobile, but a dedicated PWA with push notifications closes the loop for traders who aren't always at a desk.

### Not on the roadmap for Core (deliberate non-goals)

- **Strategy generation.** Gatekeeper helps you enforce and refine *your* strategy. It will never tell you what to trade.
- **Social features.** No leaderboards, no copy trading, no public profiles. Trading discipline is personal.

### Planned for Pro

- **Trade execution via broker bridge.** Core gates permission. Pro extends enforcement into execution — the bridge can place and manage orders when rules are satisfied, including a fully automated mode. Execution is always broker-specific and bridge-mediated, never built into Core directly.
- **Managed hosted deployment.** Self-hosted is the primary model and always will be. A managed hosted option will be offered for traders who want the system without running their own infrastructure. Hosted serves accessibility, not growth metrics.

### Open questions (no commitment yet)

- **Multi-user / team features.** Gatekeeper is a personal system today. Team or firm-level features (shared plans, role-based access, aggregate reporting) may be explored, but only if they strengthen the enforcement model — not as a generic collaboration play. This is a significant scope expansion and won't happen without a clear use case.

---

## Messaging Reference

For anyone writing about Gatekeeper — README, landing page, docs, social:

**One line:**
Enforce your trading rules.

**One paragraph:**
You define your rules, and the system enforces them before you can take a trade. Over time, it shows you which rules actually work — and keeps you accountable to them.

**The deeper idea:**
Humans break their own rules. Systems don't. Gatekeeper is the system.
