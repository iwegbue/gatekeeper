"""
MCP resources — read-only context that agents can load before acting.

Resources are fetched by URI and returned as structured text/JSON.
They are designed to be included in an agent's context window before
it decides which tools to call.
"""
import json
import logging

from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    """Register all resources onto the given FastMCP instance."""

    @mcp.resource("gatekeeper://plan")
    async def get_plan() -> str:
        """
        The active trading plan: name, description, and all rules organised by layer.
        Read this before reviewing ideas or coaching journal entries.
        """
        from app.database import AsyncSessionFactory
        from app.services import plan_service
        async with AsyncSessionFactory() as db:
            plan = await plan_service.get_plan(db)
            # get_plan auto-creates a plan row if none exists; commit so it persists
            await db.commit()
            rules_by_layer = await plan_service.get_rules_by_layer(db, plan.id)

            lines = [f"# Trading Plan: {plan.name}"]
            if plan.description:
                lines.append(f"\n{plan.description}")
            lines.append("")

            for layer, rules in rules_by_layer.items():
                lines.append(f"\n## {layer}")
                if not rules:
                    lines.append("  (no rules)")
                    continue
                for r in rules:
                    lines.append(
                        f"  - [{r.rule_type}, weight={r.weight}] {r.name}"
                        + (f": {r.description}" if r.description else "")
                    )

            return "\n".join(lines)

    @mcp.resource("gatekeeper://ideas/active")
    async def get_active_ideas() -> str:
        """
        All non-terminal ideas (not CLOSED or INVALIDATED) with their current state and grade.
        Read this to understand what setups are currently being tracked.
        """
        from app.database import AsyncSessionFactory
        from app.services import idea_service
        async with AsyncSessionFactory() as db:
            ideas = await idea_service.list_ideas(db, active_only=True)
            if not ideas:
                return "No active ideas."
            rows = []
            for i in ideas:
                rows.append({
                    "id": str(i.id),
                    "instrument": i.instrument,
                    "direction": i.direction,
                    "state": i.state,
                    "grade": i.grade,
                    "checklist_score": i.checklist_score,
                    "notes": i.notes,
                })
            return json.dumps(rows, indent=2)

    @mcp.resource("gatekeeper://trades/open")
    async def get_open_trades() -> str:
        """
        All currently open trades with entry price, SL, TP, and management state.
        Read this before making any trade management decisions.
        """
        from app.database import AsyncSessionFactory
        from app.services import trade_service
        async with AsyncSessionFactory() as db:
            trades = await trade_service.list_trades(db, open_only=True)
            if not trades:
                return "No open trades."
            rows = []
            for t in trades:
                rows.append({
                    "id": str(t.id),
                    "idea_id": str(t.idea_id),
                    "instrument": t.instrument,
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "sl_price": t.sl_price,
                    "tp_price": t.tp_price,
                    "lot_size": t.lot_size,
                    "risk_pct": t.risk_pct,
                    "grade": t.grade,
                    "partials_taken": t.partials_taken,
                    "be_locked": t.be_locked,
                    "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                })
            return json.dumps(rows, indent=2)

    @mcp.resource("gatekeeper://discipline")
    async def get_discipline() -> str:
        """
        Latest discipline snapshot: score, grade distribution, adherence trend,
        and most-violated rules. Read this for performance coaching context.
        """
        from app.database import AsyncSessionFactory
        from app.services import report_service
        async with AsyncSessionFactory() as db:
            score = await report_service.get_discipline_score(db)
            stats = await report_service.get_trade_stats(db)
            grade_dist = await report_service.get_grade_distribution(db)
            adherence = await report_service.get_plan_adherence_stats(db)
            violations = await report_service.get_rule_violation_frequency(db, limit=5)

            data = {
                "discipline_score": round(score, 1),
                "trade_stats": stats,
                "grade_distribution": grade_dist,
                "plan_adherence": adherence,
                "top_violated_rules": violations,
            }
            return json.dumps(data, indent=2)
