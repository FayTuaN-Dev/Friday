"""Un petit serveur MCP pour les tests : rien de réel, pas de réseau."""

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

server = MCPServer("faux")
notes: list[str] = []


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def add(a: int, b: int) -> str:
    """Add two numbers."""
    return str(a + b)


@server.tool()
def save_note(text: str) -> str:
    """Save a note (changes data)."""
    notes.append(text)
    return f"saved {len(notes)}"


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def fail() -> str:
    """Always fails."""
    raise ValueError("boom")


if __name__ == "__main__":
    server.run("stdio")
