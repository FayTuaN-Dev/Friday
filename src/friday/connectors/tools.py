"""Les outils d'un serveur MCP vus comme des outils de Friday, et la compétence qui les
regroupe. Nom donné au modèle : mcp_<serveur>_<outil> (deux serveurs peuvent avoir un outil
du même nom). Sans « lecture seule » déclarée par le serveur, l'outil demande un « oui »."""

import re
from typing import Any

from friday.brain.skills import Skill
from friday.connectors.link import Link
from friday.tools.base import Tool, ToolResult
from friday.voice.wake import normalize

MAX_DESCRIPTION = 400  # certaines descriptions font des pages : la mémoire de qwen est comptée
TIMEOUT = 60.0


def _short(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class McpTool(Tool):
    def __init__(self, link: Link, tool) -> None:
        self.link, self.remote = link, tool.name
        slug = re.sub(r"[^a-zA-Z0-9_]+", "_", tool.name).strip("_")
        self.name = f"mcp_{link.server.slug}_{slug}"[:64]
        self.title = tool.title or tool.name
        self.description = _short(tool.description or tool.title or tool.name, MAX_DESCRIPTION)
        schema = tool.input_schema or {}
        self.parameters = dict(schema.get("properties") or {})
        self.required = tuple(schema.get("required") or ())
        annotations = tool.annotations
        self.needs_confirmation = not (annotations and annotations.read_only_hint)
        self.timeout = TIMEOUT

    def label(self, args: dict[str, Any]) -> str:
        return f"{self.link.server.name} : {self.title}"

    def confirmation(self, args: dict[str, Any]) -> str:
        shown = ", ".join(f"{k} = {_short(str(v), 60)}" for k, v in args.items() if v != "")
        detail = f" ({shown})" if shown else ""
        return (f"Le connecteur « {self.link.server.name} » veut lancer « {self.title} »"
                f"{detail}, qui peut modifier des données. J'y vais ?")  # fmt: skip

    def run(self, **kwargs: Any) -> ToolResult:
        kwargs.pop("reason", None)  # paramètre de façade (Tool.schema), inconnu du serveur
        text, ok = self.link.call(self.remote, kwargs, self.timeout)
        return ToolResult(text, ok=ok)


def skill_for(link: Link, tools: list[McpTool]) -> Skill:
    server = link.server
    name = f"mcp_{server.slug}"
    label = f"connecteur {server.name}" + (f" : {server.description}" if server.description
                                          else "")  # fmt: skip
    lines = [
        f"- Connecteur « {server.name} »"
        + (f" ({server.description})" if server.description else "")
        + " : ses outils renvoient des données réelles ; appuie-toi dessus, n'invente pas."
    ]
    lines += [f"  - {t.name} : {_short(t.description, 160)}" for t in tools]
    keywords = {normalize(k).strip() for k in (*server.keywords, server.name)} - {""}
    examples = (server.description,) if server.description else ()
    return Skill(name, label, tuple(t.name for t in tools), "\n".join(lines),
                 tuple(sorted(keywords)), examples)  # fmt: skip
