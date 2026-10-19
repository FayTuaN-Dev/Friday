"""Les outils d'un serveur MCP vus comme des outils de Friday, et la compétence qui les
regroupe. Nom donné au modèle : mcp_<serveur>_<outil> (deux serveurs peuvent avoir un outil
du même nom). Sans « lecture seule » déclarée par le serveur, l'outil demande un « oui ».
La mémoire de qwen est comptée : les schémas sont resserrés, et un serveur ne donne que
quelques outils (les premiers, ou ceux de sa liste « outils »)."""

import json
import re
from typing import Any

from friday.brain.skills import Skill
from friday.connectors.link import Link
from friday.tools.base import Tool, ToolResult
from friday.voice.wake import normalize

MAX_DESCRIPTION = 400  # certaines descriptions font des pages
MAX_PARAM_TEXT = 120  # description d'un paramètre
MAX_SCHEMA = 2500  # caractères : un outil plus lourd n'est pas pris d'office
MAX_TOOLS = 10  # par serveur, sans liste « outils » (Notion en propose 65)
MAX_TOTAL = 12000  # caractères de schémas par serveur, liste ou pas (~3 000 jetons)
TIMEOUT = 60.0


def _short(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# des précisions de validation que le serveur vérifie lui-même : inutiles au modèle
DROPPED = {"$schema", "examples", "pattern", "format", "minLength", "maxLength", "minItems",
           "maxItems", "additionalProperties", "propertyNames"}  # fmt: skip


def compact(node: Any, nested: bool = False) -> Any:
    """Un paramètre sans ce qui ne sert pas au modèle : sa description raccourcie, et pas
    celles de ses sous-champs (Notion en écrit des pages)."""
    if isinstance(node, list):
        return [compact(v, nested) for v in node]
    if not isinstance(node, dict):
        return node
    result = {}
    for key, value in node.items():
        if key in DROPPED:
            continue
        if key == "description" and isinstance(value, str):
            if not nested:
                result[key] = _short(value, MAX_PARAM_TEXT)
            continue
        result[key] = compact(value, True)
    return result


class McpTool(Tool):
    def __init__(self, link: Link, tool) -> None:
        self.link, self.remote = link, tool.name
        slug = re.sub(r"[^a-zA-Z0-9_]+", "_", tool.name).strip("_")
        self.name = f"mcp_{link.server.slug}_{slug}"[:64]
        self.title = tool.title or tool.name
        self.description = _short(tool.description or tool.title or tool.name, MAX_DESCRIPTION)
        schema = tool.input_schema or {}
        properties = schema.get("properties") or {}
        self.parameters = {name: compact(value) for name, value in properties.items()}
        self.required = tuple(schema.get("required") or ())
        annotations = tool.annotations
        self.needs_confirmation = not (annotations and annotations.read_only_hint)
        self.timeout = TIMEOUT

    @property
    def size(self) -> int:
        return len(json.dumps(self.schema(), ensure_ascii=False))

    def label(self, args: dict[str, Any]) -> str:
        return f"{self.link.server.name} : {self.title}"

    def confirmation(self, args: dict[str, Any]) -> str:
        shown = ", ".join(f"{k} = {_short(str(v), 60)}" for k, v in args.items() if v != "")
        detail = f" ({shown})" if shown else ""
        return (f"Le connecteur « {self.link.server.name} » veut lancer « {self.title} »"
                f"{detail}, qui peut modifier des données. J'y vais ?")  # fmt: skip

    def run(self, **kwargs: Any) -> ToolResult:
        kwargs.pop("reason", None)  # paramètre de façade (Tool.schema), inconnu du serveur
        # qwen remplit volontiers les champs facultatifs avec null ou "" : le serveur refuse
        args = {k: v for k, v in kwargs.items()
                if v is not None and (v != "" or k in self.required)}  # fmt: skip
        text, ok = self.link.call(self.remote, args, self.timeout)
        return ToolResult(text, ok=ok)


def pick(tools: list[McpTool], wanted: tuple[str, ...] = ()) -> list[McpTool]:
    """Les outils donnés au modèle : ceux de la liste « outils » du fichier (dans son ordre),
    sinon les premiers assez légers, lecture seule d'abord ; sans dépasser MAX_TOTAL."""
    if wanted:
        by_name = {t.remote: t for t in tools}
        candidates = [by_name[name] for name in wanted if name in by_name]
    else:
        light = [t for t in tools if t.size <= MAX_SCHEMA]
        candidates = sorted(light, key=lambda t: t.needs_confirmation)[:MAX_TOOLS]
    chosen, total = [], 0
    for tool in candidates:
        if total + tool.size <= MAX_TOTAL:
            chosen.append(tool)
            total += tool.size
    return chosen


def skill_for(link: Link, tools: list[McpTool]) -> Skill:
    server = link.server
    name = f"mcp_{server.slug}"
    label = f"connecteur {server.name}" + (f" : {server.description}" if server.description
                                          else "")  # fmt: skip
    lines = [
        f"- Connecteur « {server.name} »"
        + (f" ({server.description})" if server.description else "")
        + " : ses outils renvoient des données réelles et à jour. Quand la demande en parle, "
        "utilise-les en priorité, avant web_search, market_quote ou la bibliothèque ; "
        "appuie-toi sur ce qu'ils renvoient, n'invente pas."
    ]
    lines += [f"  - {t.name} : {_short(t.description, 160)}" for t in tools]
    keywords = {normalize(k).strip() for k in (*server.keywords, server.name)} - {""}
    examples = (server.description,) if server.description else ()
    return Skill(name, label, tuple(t.name for t in tools), "\n".join(lines),
                 tuple(sorted(keywords)), examples)  # fmt: skip
