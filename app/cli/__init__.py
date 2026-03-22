"""
gk — Gatekeeper CLI

A command-line interface for interacting with a running Gatekeeper Core instance
via its JSON API. Useful for scripting, cron automation, and launching the MCP
stdio server for Claude Desktop / Cursor integration.

Configuration (in order of precedence):
  1. CLI flags (--url, --token)
  2. Environment variables: GK_API_URL, GK_API_TOKEN
  3. Config file: ~/.config/gatekeeper/config.toml
"""
