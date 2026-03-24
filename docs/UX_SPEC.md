# Gatekeeper UX Spec

This document is the canonical reference for design, language, and UX decisions in Gatekeeper.
All contributors — human and AI — must follow it when writing or reviewing UI-facing code.

---

## Audience

Gatekeeper is used by traders at all levels of experience:

- **Beginners** new to rule-based systems. They may not know what R-multiples, SL/TP, or breakeven management mean. They have never seen a 7-layer checklist before.
- **Intermediate traders** who know the terminology and have some trading experience but are new to enforcing their process with software.
- **Advanced traders** with defined systems, established vocabulary, and strong opinions about what they need.

**Design for all three.** The product must be self-evident to a beginner on first encounter, and must never feel dumbed down to an advanced trader. The tool for this is **progressive clarity**: explain at the surface, reveal depth on demand.

**What we cannot assume** about any user on first encounter:
- Knowledge of trading jargon (SL, TP, BE, R-multiple, partials, confluence)
- Familiarity with rule-based trading or systematic process
- Technical comfort with Docker, databases, API keys, or command-line tools
- Prior experience with Gatekeeper or similar tools

---

## Design Principles

### 1. Progressive clarity
The simplest mental model is always available. Depth — advanced options, detailed calculations, edge-case controls — is available but not forced. Lead with the human-readable label; provide the technical identifier only where it's useful (e.g., API/CLI docs).

### 2. Explain before blocking
When the system can't proceed (a rule is unmet, a transition is blocked), it must say why in plain language. Never show a disabled button without an explanation of what needs to happen first.

### 3. Contextual help over documentation
The answer to "what does this mean?" should be one hover or one click away from where the question arises. The help page is a reference, not a first resort.

### 4. No jargon without definition
Every abbreviation (SL, TP, BE, R) must be introduced with its full form on its first appearance on a page. Every calculated metric shown in the UI must have an inline tooltip that says what it is AND how it is calculated.

### 5. Actions must describe their consequences
Every button that causes a state change, data loss, or irreversible action must have a brief inline description — not just a label. "Invalidate" alone is not enough. "Invalidate — use this when the setup no longer meets your criteria but you want to keep a record" is.

### 6. Surface the recommended path first
When there are multiple ways to do something, the easiest or most appropriate path for most users should be the primary CTA. Advanced or manual alternatives are secondary. "Start Plan Builder (recommended)" before "build manually".

### 7. State must be readable without the help page
Every state badge, progress indicator, and status label must be understandable to a new user without reading documentation. Use human-readable display labels; reserve enum values for the API.

---

## Terminology Glossary

These are the canonical definitions for all terms used in the Gatekeeper UI. Use these exact words and definitions consistently across templates, tooltips, help text, and documentation. Do not invent synonyms.

| Term | Definition |
|------|-----------|
| **Idea** | A potential trade you're evaluating. You track it through a checklist before deciding whether to take it. |
| **Layer** | One of the 7 categories of rules in your trading plan. Each layer represents a stage of analysis (Context, Setup, Confirmation, Entry, Risk, Management, Behavioral). |
| **Rule** | A specific condition within a layer that your trade must meet. You define the rules; Gatekeeper enforces them. |
| **Required rule** | A rule that must be checked before you can advance to the next layer. Skipping a required rule blocks progression. |
| **Optional rule** | A rule that improves your grade if checked, but won't block you from advancing. Use for conditions that strengthen a setup without being mandatory. |
| **Advisory rule** | A reminder only. Checking or skipping an advisory rule has no effect on your grade or ability to advance. Use for habits or prompts you want to see. |
| **Checklist** | The full set of rules for an idea, organised by layer. Working through the checklist is how you evaluate a setup. |
| **Grade** | A letter (A, B, or C) that reflects the quality of your setup — not whether the trade was profitable. A = 85%+ of points checked, B = 65–84%, C = below 65%. |
| **Checklist score** | The total points earned from checked rules, divided by the total possible points. Determines your grade. |
| **Weight** | How much a rule contributes to your checklist score. 1 = minor, 2 = moderate, 3 = critical. Advisory rules have no weight. |
| **State** | Where an idea is in the evaluation process. See the State Reference section below. |
| **Discipline Score** | A 0–100 score measuring how consistently you follow your rules. Combines plan adherence, grade distribution, and rule violation rate. Aim for 70+. |
| **Plan adherence** | The percentage of Required rules you checked before acting. 100% means you checked every required rule. Aim for 100% on every trade. |
| **Entry window** | An optional time period during which you plan to enter a trade. Once it expires, the idea is automatically invalidated. Use it when the opportunity has a time constraint. |
| **R-multiple** | How many times your initial risk (entry to stop loss distance) a trade made or lost. A 2R trade made twice your risk. A -1R trade lost your full risk. |
| **SL** | Stop Loss — the price at which you exit to cap your loss on a trade. |
| **TP** | Take Profit — a target price at which you plan to exit with a gain. |
| **Initial SL** | The stop loss at the time you opened the trade. Used to calculate R-multiples. May differ from the current SL if you've trailed or moved it. |
| **BE** / **Breakeven** | Moving your stop loss to your entry price. Worst case becomes a scratch trade (no loss). |
| **Partials** / **Partial exits** | Scaling out of part of your position at a target level. Locks in some profit while letting the rest of the trade run. |
| **Plan** | Your trading plan: a named set of rules organised across the 7 layers. Only one plan is active at a time. |
| **Plan validation** | A check that your rules are testable and coherent — that they describe measurable conditions, not vague intentions. |
| **Journal** | A post-trade review automatically created when you close a trade. Includes what went well, what went wrong, lessons, and emotional state. |
| **Violation** | A Required rule that was not checked before you advanced or opened a trade. Tracked in the journal and reports. |

---

## State Reference

Ideas move through these states as you work the checklist. Display the human-readable label in the UI. Use the enum value only in API/CLI documentation.

| Display label | Enum value | Meaning |
|--------------|-----------|---------|
| Watching | `WATCHING` | You've spotted an opportunity and are monitoring it. |
| Context & Setup Valid | `SETUP_VALID` | Context and Setup layer rules are satisfied. |
| Confirmed | `CONFIRMED` | Confirmation layer rules are satisfied. |
| Entry Permitted | `ENTRY_PERMITTED` | All pre-entry rules are satisfied. You may open a trade. |
| In Trade | `IN_TRADE` | A trade is open. |
| Managed | `MANAGED` | The trade has been actively managed (SL moved, partials taken, etc.). |
| Closed | `CLOSED` | The trade is closed. |
| Invalidated | `INVALIDATED` | The setup was abandoned. The idea is kept as a record. |

---

## Grading Reference

| Grade | Threshold | Meaning |
|-------|-----------|---------|
| A | 85%+ of possible points | High-quality setup. Most or all rules checked. |
| B | 65–84% | Good setup. Some optional rules missed. |
| C | Below 65% | Low-quality setup. Many rules unchecked. |

Grade measures compliance with your own rules, not profitability. A C-grade winner is still a discipline problem. An A-grade loser is a good trade that didn't work out.

---

## Abbreviation Rules

Introduce every abbreviation with its full form on its first appearance on each page. Use an HTML `<abbr>` tag:

```html
<abbr title="Stop Loss">SL</abbr>
<abbr title="Take Profit">TP</abbr>
<abbr title="Breakeven">BE</abbr>
<abbr title="Risk multiple — how many times your initial risk this trade made or lost">R</abbr>
```

After the first use on a page, you may use the abbreviation alone.

---

## Tooltip Standards

Every tooltip must answer: **what is this, and why does it matter?**

- **Metrics and scores**: state what the value is AND how it is calculated. Example: "Discipline Score (0–100) — measures how consistently you follow your rules. Combines plan adherence, grade distribution, and violation rate."
- **Action buttons**: state what will happen if you click. Example: "Invalidate — marks this idea as abandoned. The record is kept for review. Use when the setup no longer qualifies."
- **Field labels**: define the field and give an example. Example: "Entry Window — the time period during which you plan to enter. Expires automatically. E.g. set to end-of-session for day trades."
- **Rule types**: explain the distinction from other types. Example: "Optional — checking this improves your grade. Skipping it won't block you, but it lowers your score."

---

## Progressive Disclosure

Advanced or rarely-needed options should not crowd the primary workflow. Use these patterns:

- **"Advanced" toggle / `<details>` block**: for model overrides, custom weights, edge-case settings
- **Secondary link below primary CTA**: "or build manually" after "Start Plan Builder (recommended)"
- **Collapsible sections**: for layer-by-layer rule breakdowns, verbose explanations, reference data

Do not hide essential information — only optional complexity.

---

## Error Messages

Error messages must be specific and actionable.

| Situation | Bad | Good |
|-----------|-----|------|
| Guard block | "Cannot advance" | "Context layer has 2 unchecked Required rules. Check them to continue." |
| Invalid input | "Invalid value" | "Risk % must be between 0.1 and 100." |
| State conflict | "Conflict" | "This idea is already in trade. You cannot edit the checklist once a trade is open." |

---

## Changelog

- 2026-03-24: Initial spec created from UX audit for beginner/advanced trader accessibility.
