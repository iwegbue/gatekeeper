"""
MCP server factory for Gatekeeper Core.

Creates a FastMCP instance with all tools and resources registered.
The server is mounted into the main FastAPI app at /mcp.
"""

import logging

from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    mcp = FastMCP(
        name="Gatekeeper",
        instructions=(
            "Gatekeeper is a single-user trading discipline platform. "
            "It enforces a 7-layer rule-based trading plan via a layer-gated state machine. "
            "Use the resources to read context (plan, active ideas, open trades, discipline stats) "
            "before calling tools that mutate state. "
            "Idea states flow: WATCHING → SETUP_VALID → CONFIRMED → ENTRY_PERMITTED → IN_TRADE → MANAGED → CLOSED. "
            "Advancement requires all REQUIRED rules in the current layer to be checked. "
            "The state machine will raise an error if guards are not met — read the error and "
            "surface it to the user rather than retrying blindly."
        ),
    )

    # Register all tools and resources
    from app.mcp import resources, tools  # noqa: F401 — side-effect registration

    # Attach the tool/resource modules to the mcp instance so decorators work
    tools.register(mcp)
    resources.register(mcp)

    return mcp
