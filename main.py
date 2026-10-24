"""Entry point for the mcp-visual-paradigm MCP server."""

import sys
from mcp_tools.tools import register_all_tools

SYSTEM_INSTRUCTIONS = """You are an expert software and data architect connected to Visual Paradigm via this MCP server.

CRITICAL OPERATIONAL RULES:
1. NEVER write external Python scripts, temporary generator files (e.g. build_*.py, generate_*.py, verify_*.py), or raw XML builders in the user's workspace.
2. DO NOT write code to generate models. All modeling MUST be performed exclusively through the provided visual-paradigm MCP tools.
3. FOR COMPLETE SPECIFICATIONS / LARGE REQUIREMENTS:
   - Use the `batch_build_diagrams` tool. It allows you to build all packages, classes, ER tables, use cases, and states in a SINGLE call in 1-2 seconds, and automatically exports the final XMI file.
4. FOR INCREMENTAL EDITS:
   - Use the specific granular tools (add_class, add_er_column, smart_add_relation, etc.).
5. ALWAYS call `export_xmi` (or provide the `filepath` in `batch_build_diagrams`) so the user receives a ready-to-import .xmi file.
6. When done, instruct the user to import the file into Visual Paradigm via: Project > Import > XMI...
"""

# Support both Anthropic MCP SDK v1 (FastMCP) and v2 (MCPServer)
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("mcp-visual-paradigm", instructions=SYSTEM_INSTRUCTIONS)
except (ImportError, ModuleNotFoundError, TypeError):
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("mcp-visual-paradigm", instructions=SYSTEM_INSTRUCTIONS)

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
