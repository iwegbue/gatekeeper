"""
gk — Gatekeeper CLI entry point.

Usage:
  gk status
  gk ideas list [--active] [--instrument EURUSD] [--json]
  gk ideas show <id>
  gk ideas create --instrument EURUSD --direction LONG [--notes "..."] [--risk 1.0]
  gk ideas advance <id> [--reason "..."]
  gk ideas regress <id> [--reason "..."]
  gk ideas invalidate <id> [--reason "..."]
  gk ideas check <idea_id> <check_id> [--uncheck] [--notes "..."]
  gk trades list [--open] [--json]
  gk trades show <id>
  gk trades open <idea_id> --entry 1.2650 --sl 1.2600 [--tp 1.2750] [--size 0.5] [--risk 1.0]
  gk trades close <id> --exit 1.2700
  gk trades update-sl <id> --sl 1.2620
  gk trades partial <id>
  gk trades be <id>
  gk journal list [--completed] [--json]
  gk journal show <id>
  gk journal edit <id> [--well "..."] [--wrong "..."] [--lessons "..."] [--emotions "..."] [--no-retake]
  gk journal complete <id>
  gk plan show [--json]
  gk report discipline [--json]
  gk ai review <idea_id>
  gk ai coach <journal_id>
  gk mcp [--transport stdio|sse] [--port 3001]
  gk config set --url http://localhost:8000 --token gk_xxx
"""
import json as _json
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from app.cli.client import GatekeeperClient
from app.cli.config import resolve_token, resolve_url, save_config

app = typer.Typer(
    name="gk",
    help="Gatekeeper CLI — interact with your trading discipline platform.",
    no_args_is_help=True,
)
console = Console()

# ── Global options ──────────────────────────────────────────────────────────

_url_opt = Annotated[Optional[str], typer.Option("--url", envvar="GK_API_URL", help="Gatekeeper base URL")]
_token_opt = Annotated[Optional[str], typer.Option("--token", envvar="GK_API_TOKEN", help="API bearer token")]
_json_opt = Annotated[bool, typer.Option("--json", help="Output raw JSON")]


def _client(url: str | None, token: str | None) -> GatekeeperClient:
    base = resolve_url(url)
    tok = resolve_token(token)
    if not tok:
        console.print("[red]No API token found. Set GK_API_TOKEN or run: gk config set[/red]")
        raise typer.Exit(1)
    return GatekeeperClient(base, tok)


def _dump(data, as_json: bool) -> None:
    if as_json:
        typer.echo(_json.dumps(data, indent=2))
    else:
        rprint(data)


# ── status ──────────────────────────────────────────────────────────────────

@app.command()
def status(
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Show app health, version, and active counts."""
    c = _client(url, token)
    data = c.get("/api/v1/status")
    _dump(data, output_json)


# ── ideas ───────────────────────────────────────────────────────────────────

ideas_app = typer.Typer(help="Manage trading ideas.", no_args_is_help=True)
app.add_typer(ideas_app, name="ideas")


@ideas_app.command("list")
def ideas_list(
    active: Annotated[bool, typer.Option("--active", help="Only active ideas")] = False,
    instrument: Annotated[Optional[str], typer.Option("--instrument", help="Filter by symbol")] = None,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """List trading ideas."""
    c = _client(url, token)
    data = c.get("/api/v1/ideas", active_only=active, instrument=instrument)
    if output_json:
        typer.echo(_json.dumps(data, indent=2))
        return
    table = Table("ID (short)", "Instrument", "Direction", "State", "Grade", "Score%")
    for i in data:
        table.add_row(
            i["id"][:8],
            i["instrument"],
            i["direction"],
            i["state"],
            i.get("grade") or "-",
            str(i.get("score_pct") or "-"),
        )
    console.print(table)


@ideas_app.command("show")
def ideas_show(
    idea_id: Annotated[str, typer.Argument(help="Idea UUID")],
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Show full detail for an idea including its checklist."""
    c = _client(url, token)
    data = c.get(f"/api/v1/ideas/{idea_id}")
    _dump(data, output_json)


@ideas_app.command("create")
def ideas_create(
    instrument: Annotated[str, typer.Option("--instrument", "-i", help="Symbol e.g. EURUSD")],
    direction: Annotated[str, typer.Option("--direction", "-d", help="LONG or SHORT")],
    notes: Annotated[Optional[str], typer.Option("--notes", "-n", help="Setup notes")] = None,
    risk: Annotated[Optional[float], typer.Option("--risk", help="Risk % (e.g. 1.0)")] = None,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Create a new trading idea."""
    c = _client(url, token)
    payload = {"instrument": instrument, "direction": direction}
    if notes:
        payload["notes"] = notes
    if risk is not None:
        payload["risk_pct"] = risk
    data = c.post("/api/v1/ideas", json=payload)
    _dump(data, output_json)


@ideas_app.command("advance")
def ideas_advance(
    idea_id: Annotated[str, typer.Argument(help="Idea UUID")],
    reason: Annotated[Optional[str], typer.Option("--reason", help="Reason for advance")] = None,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Advance an idea to the next state."""
    c = _client(url, token)
    payload = {}
    if reason:
        payload["reason"] = reason
    data = c.post(f"/api/v1/ideas/{idea_id}/advance", json=payload)
    _dump(data, output_json)


@ideas_app.command("regress")
def ideas_regress(
    idea_id: Annotated[str, typer.Argument(help="Idea UUID")],
    reason: Annotated[Optional[str], typer.Option("--reason", help="Reason for regression")] = None,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Regress an idea one step back."""
    c = _client(url, token)
    payload = {}
    if reason:
        payload["reason"] = reason
    data = c.post(f"/api/v1/ideas/{idea_id}/regress", json=payload)
    _dump(data, output_json)


@ideas_app.command("invalidate")
def ideas_invalidate(
    idea_id: Annotated[str, typer.Argument(help="Idea UUID")],
    reason: Annotated[Optional[str], typer.Option("--reason", help="Reason for invalidation")] = None,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Invalidate an idea."""
    c = _client(url, token)
    payload = {}
    if reason:
        payload["reason"] = reason
    data = c.post(f"/api/v1/ideas/{idea_id}/invalidate", json=payload)
    _dump(data, output_json)


@ideas_app.command("check")
def ideas_check(
    idea_id: Annotated[str, typer.Argument(help="Idea UUID")],
    check_id: Annotated[str, typer.Argument(help="Checklist item UUID")],
    uncheck: Annotated[bool, typer.Option("--uncheck", help="Uncheck instead of check")] = False,
    notes: Annotated[Optional[str], typer.Option("--notes", help="Notes for this check")] = None,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Toggle a rule check on an idea's checklist."""
    c = _client(url, token)
    payload: dict = {"checked": not uncheck}
    if notes:
        payload["notes"] = notes
    data = c.post(f"/api/v1/ideas/{idea_id}/checks/{check_id}", json=payload)
    _dump(data, output_json)


# ── trades ──────────────────────────────────────────────────────────────────

trades_app = typer.Typer(help="Manage trades.", no_args_is_help=True)
app.add_typer(trades_app, name="trades")


@trades_app.command("list")
def trades_list(
    open_only: Annotated[bool, typer.Option("--open", help="Only open trades")] = False,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """List trades."""
    c = _client(url, token)
    data = c.get("/api/v1/trades", open_only=open_only)
    if output_json:
        typer.echo(_json.dumps(data, indent=2))
        return
    table = Table("ID (short)", "Instrument", "Direction", "State", "Entry", "SL", "R")
    for t in data:
        table.add_row(
            t["id"][:8],
            t["instrument"],
            t["direction"],
            t["state"],
            str(t.get("entry_price") or "-"),
            str(t.get("sl_price") or "-"),
            str(t.get("r_multiple") or "-"),
        )
    console.print(table)


@trades_app.command("show")
def trades_show(
    trade_id: Annotated[str, typer.Argument(help="Trade UUID")],
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Show full detail for a trade."""
    c = _client(url, token)
    data = c.get(f"/api/v1/trades/{trade_id}")
    _dump(data, output_json)


@trades_app.command("open")
def trades_open(
    idea_id: Annotated[str, typer.Argument(help="ENTRY_PERMITTED idea UUID")],
    entry: Annotated[float, typer.Option("--entry", help="Entry price")],
    sl: Annotated[float, typer.Option("--sl", help="Stop loss price")],
    tp: Annotated[Optional[float], typer.Option("--tp", help="Take profit price")] = None,
    size: Annotated[Optional[float], typer.Option("--size", help="Lot size")] = None,
    risk: Annotated[Optional[float], typer.Option("--risk", help="Risk % override")] = None,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Open a trade from an ENTRY_PERMITTED idea."""
    c = _client(url, token)
    payload: dict = {"entry_price": entry, "sl_price": sl}
    if tp is not None:
        payload["tp_price"] = tp
    if size is not None:
        payload["lot_size"] = size
    if risk is not None:
        payload["risk_pct"] = risk
    data = c.post(f"/api/v1/ideas/{idea_id}/trade", json=payload)
    _dump(data, output_json)


@trades_app.command("close")
def trades_close(
    trade_id: Annotated[str, typer.Argument(help="Trade UUID")],
    exit_price: Annotated[float, typer.Option("--exit", help="Exit price")],
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Close an open trade."""
    c = _client(url, token)
    data = c.post(f"/api/v1/trades/{trade_id}/close", json={"exit_price": exit_price})
    _dump(data, output_json)


@trades_app.command("update-sl")
def trades_update_sl(
    trade_id: Annotated[str, typer.Argument(help="Trade UUID")],
    sl: Annotated[float, typer.Option("--sl", help="New stop loss price")],
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Update the stop loss on an open trade."""
    c = _client(url, token)
    data = c.post(f"/api/v1/trades/{trade_id}/update-sl", json={"sl_price": sl})
    _dump(data, output_json)


@trades_app.command("partial")
def trades_partial(
    trade_id: Annotated[str, typer.Argument(help="Trade UUID")],
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Record a partial close on an open trade."""
    c = _client(url, token)
    data = c.post(f"/api/v1/trades/{trade_id}/partial")
    _dump(data, output_json)


@trades_app.command("be")
def trades_be(
    trade_id: Annotated[str, typer.Argument(help="Trade UUID")],
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Lock breakeven on an open trade."""
    c = _client(url, token)
    data = c.post(f"/api/v1/trades/{trade_id}/be")
    _dump(data, output_json)


# ── journal ─────────────────────────────────────────────────────────────────

journal_app = typer.Typer(help="Manage journal entries.", no_args_is_help=True)
app.add_typer(journal_app, name="journal")


@journal_app.command("list")
def journal_list(
    completed: Annotated[bool, typer.Option("--completed", help="Only completed entries")] = False,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """List journal entries."""
    c = _client(url, token)
    data = c.get("/api/v1/journal")
    if completed:
        data = [e for e in data if e.get("completed")]
    if output_json:
        typer.echo(_json.dumps(data, indent=2))
        return
    table = Table("ID (short)", "Trade ID (short)", "Adherence%", "Completed", "Would Retake")
    for e in data:
        table.add_row(
            e["id"][:8],
            e.get("trade_id", "")[:8],
            str(e.get("plan_adherence_pct") or "-"),
            "✓" if e.get("completed") else "✗",
            str(e.get("would_take_again") or "-"),
        )
    console.print(table)


@journal_app.command("show")
def journal_show(
    entry_id: Annotated[str, typer.Argument(help="Journal entry UUID")],
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Show full detail for a journal entry."""
    c = _client(url, token)
    data = c.get(f"/api/v1/journal/{entry_id}")
    _dump(data, output_json)


@journal_app.command("edit")
def journal_edit(
    entry_id: Annotated[str, typer.Argument(help="Journal entry UUID")],
    well: Annotated[Optional[str], typer.Option("--well", help="What went well")] = None,
    wrong: Annotated[Optional[str], typer.Option("--wrong", help="What went wrong")] = None,
    lessons: Annotated[Optional[str], typer.Option("--lessons", help="Lessons learned")] = None,
    emotions: Annotated[Optional[str], typer.Option("--emotions", help="Emotional state")] = None,
    no_retake: Annotated[bool, typer.Option("--no-retake", help="Mark would NOT take again")] = False,
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Update reflective fields on a journal entry."""
    c = _client(url, token)
    payload: dict = {}
    if well is not None:
        payload["what_went_well"] = well
    if wrong is not None:
        payload["what_went_wrong"] = wrong
    if lessons is not None:
        payload["lessons_learned"] = lessons
    if emotions is not None:
        payload["emotions"] = emotions
    if no_retake:
        payload["would_take_again"] = False
    data = c.patch(f"/api/v1/journal/{entry_id}", json=payload)
    _dump(data, output_json)


@journal_app.command("complete")
def journal_complete(
    entry_id: Annotated[str, typer.Argument(help="Journal entry UUID")],
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Mark a journal entry as complete."""
    c = _client(url, token)
    data = c.post(f"/api/v1/journal/{entry_id}/complete")
    _dump(data, output_json)


# ── plan ─────────────────────────────────────────────────────────────────────

plan_app = typer.Typer(help="View the trading plan.", no_args_is_help=True)
app.add_typer(plan_app, name="plan")


@plan_app.command("show")
def plan_show(
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Show the active trading plan and all rules."""
    c = _client(url, token)
    data = c.get("/api/v1/plan")
    if output_json:
        typer.echo(_json.dumps(data, indent=2))
        return
    console.print(f"[bold]{data.get('name', 'Trading Plan')}[/bold]")
    if data.get("description"):
        console.print(data["description"])
    for layer, rules in data.get("rules_by_layer", {}).items():
        console.print(f"\n[cyan]{layer}[/cyan]")
        for r in rules:
            marker = f"[{r['rule_type']}, w={r['weight']}]"
            console.print(f"  {marker} {r['name']}")
            if r.get("description"):
                console.print(f"      {r['description']}", style="dim")


# ── report ───────────────────────────────────────────────────────────────────

report_app = typer.Typer(help="View discipline reports.", no_args_is_help=True)
app.add_typer(report_app, name="report")


@report_app.command("discipline")
def report_discipline(
    url: _url_opt = None,
    token: _token_opt = None,
    output_json: _json_opt = False,
):
    """Show the discipline report."""
    c = _client(url, token)
    data = c.get("/api/v1/reports/discipline")
    _dump(data, output_json)


# ── ai ───────────────────────────────────────────────────────────────────────

ai_app = typer.Typer(help="AI-powered analysis.", no_args_is_help=True)
app.add_typer(ai_app, name="ai")


@ai_app.command("review")
def ai_review(
    idea_id: Annotated[str, typer.Argument(help="Idea UUID")],
    url: _url_opt = None,
    token: _token_opt = None,
):
    """Run an AI review of an idea against the trading plan."""
    c = _client(url, token)
    data = c.post(f"/api/v1/ai/idea-review/{idea_id}")
    console.print(data.get("content", data))


@ai_app.command("coach")
def ai_coach(
    entry_id: Annotated[str, typer.Argument(help="Journal entry UUID")],
    url: _url_opt = None,
    token: _token_opt = None,
):
    """Run AI coaching on a journal entry."""
    c = _client(url, token)
    data = c.post(f"/api/v1/ai/journal-coach/{entry_id}")
    console.print(data.get("content", data))


# ── mcp ──────────────────────────────────────────────────────────────────────

@app.command()
def mcp(
    transport: Annotated[str, typer.Option("--transport", help="Transport: stdio or sse")] = "stdio",
    port: Annotated[int, typer.Option("--port", help="Port for SSE transport")] = 3001,
):
    """
    Launch the Gatekeeper MCP server.

    For Claude Desktop / Cursor integration (stdio):
      gk mcp

    For remote SSE access:
      gk mcp --transport sse --port 3001

    Example claude_desktop_config.json entry:
      {
        "mcpServers": {
          "gatekeeper": {
            "command": "gk",
            "args": ["mcp"],
            "env": {
              "DATABASE_URL": "postgresql+asyncpg://...",
              "SKIP_SECURITY_CHECKS": "1"
            }
          }
        }
      }
    """
    from app.mcp import create_mcp_server
    server = create_mcp_server()
    if transport == "stdio":
        server.run(transport="stdio")
    elif transport == "sse":
        server.run(transport="sse", port=port)
    else:
        console.print(f"[red]Unknown transport: {transport}. Use 'stdio' or 'sse'.[/red]")
        raise typer.Exit(1)


# ── config ───────────────────────────────────────────────────────────────────

config_app = typer.Typer(help="Manage CLI configuration.", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("set")
def config_set(
    url: Annotated[str, typer.Option("--url", help="Gatekeeper base URL")] = "http://localhost:8000",
    token: Annotated[str, typer.Option("--token", help="API bearer token")] = "",
):
    """Save URL and token to ~/.config/gatekeeper/config.toml."""
    if not token:
        console.print("[red]--token is required[/red]")
        raise typer.Exit(1)
    save_config(url, token)
    console.print("[green]Config saved to ~/.config/gatekeeper/config.toml[/green]")
    console.print(f"  url   = {url}")
    console.print(f"  token = {token[:8]}...")


@config_app.command("show")
def config_show():
    """Show current resolved configuration."""
    url = resolve_url()
    token = resolve_token()
    console.print(f"url   = {url}")
    console.print(f"token = {(token[:8] + '...') if token else '[not set]'}")


def main():
    app()


if __name__ == "__main__":
    main()
