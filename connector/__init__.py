"""Connector Agent — bridges SmartShop to FastMCP protocol.

This package exposes SmartShop's agents as a standard MCP server via FastMCP,
allowing external MCP clients (ChatGPT, Claude Desktop, Facebook Messenger, etc.)
to interact with the shop using pure text.

Run:
    python -m connector.agent              # stdio (for Claude Desktop, etc.)
    python -m connector.agent --transport sse   # SSE for HTTP clients

Or programmatically:
    from connector import run
    run()       # starts stdio server
    run("sse")  # starts SSE server
"""

from pathlib import Path

# ── Path isolation ────────────────────────────────────────────────────────────
# When connector/ is imported as a package, we need to ensure parent directory
# is on sys.path so we can import SmartShop's modules (config, database, etc.)
# without triggering a namespace collision with the official `mcp` SDK.

_parent = Path(__file__).resolve().parent.parent
if str(_parent) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_parent))

__all__ = ["run"]


def run(transport: str = "stdio") -> None:
    """Run the SmartShop MCP Connector server.

    Args:
        transport: "stdio" (default, for Claude Desktop) or "sse" (for HTTP).
    """
    from connector.connector_agent import mcp

    if transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run()
