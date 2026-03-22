"""
Gatekeeper MCP server — exposes trading discipline operations as MCP tools
and resources for Claude, Cursor, and other MCP-compatible agents.

Mount point: /mcp (StreamableHTTP transport)
"""

from app.mcp.server import create_mcp_server

__all__ = ["create_mcp_server"]
