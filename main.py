"""Entry point for the mcp-visual-paradigm MCP server."""

import sys
from mcp_tools.tools import register_all_tools

# Support both Anthropic MCP SDK v1 (FastMCP) and v2 (MCPServer)
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("mcp-visual-paradigm")
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("mcp-visual-paradigm")

# Register all architecture and diagram tools
register_all_tools(mcp)


def main() -> None:
    """Run the MCP server over standard input/output (stdio)."""
    try:
        mcp.run(transport="stdio")
    except TypeError:
        # Fallback for SDK variants where run defaults to stdio
        mcp.run()


if __name__ == "__main__":
    main()
