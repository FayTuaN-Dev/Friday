"""Outil : lire le contenu principal d'une page web (sans menus ni publicités)."""

import trafilatura

from friday.tools.base import Display, Tool, ToolResult

LLM_MAX_CHARS = 4000  # ce que le LLM lit (sa mémoire de travail est limitée)
DISPLAY_MAX_CHARS = 30_000


class ReadWebPageTool(Tool):
    name = "read_webpage"
    description = (
        "Lit le contenu d'une page web à partir de son adresse. À utiliser pour obtenir "
        "les détails d'un résultat de recherche, ou quand l'utilisateur donne un lien."
    )
    parameters = {"url": {"type": "string", "description": "Adresse complète de la page"}}
    required = ("url",)

    def label(self, args: dict) -> str:
        return f"📄 Lecture : {args.get('url', '')}"

    def run(self, url: str) -> ToolResult:
        html = trafilatura.fetch_url(url)
        text = trafilatura.extract(html) if html else None
        if not text:
            return ToolResult(f"Impossible de lire la page {url}.")
        meta = trafilatura.extract_metadata(html)
        title = (meta.title if meta and meta.title else url).strip()
        return ToolResult(
            text=f"Contenu de « {title} » ({url}) :\n{text[:LLM_MAX_CHARS]}",
            display=Display("article", title, {"url": url, "text": text[:DISPLAY_MAX_CHARS]}),
        )
