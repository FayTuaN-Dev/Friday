"""Outil : recherche sur internet (DuckDuckGo, gratuit et sans clé)."""

from ddgs import DDGS

from friday.tools.base import Display, Tool, ToolResult, retry


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Recherche sur internet. À utiliser pour l'actualité, les faits récents, les prix, "
        "les horaires, la météo, ou dès que tu n'es pas sûr d'une information."
    )
    parameters = {"query": {"type": "string", "description": "La recherche, en mots-clés"}}
    required = ("query",)

    def __init__(self, region: str = "fr-fr", max_results: int = 5, backend: str = "auto") -> None:
        self.region = region
        self.max_results = max_results
        self.backend = backend  # « auto » : ddgs passe d'un moteur à l'autre si l'un refuse

    def label(self, args: dict) -> str:
        return f"🔎 Recherche : {args.get('query', '')}"

    def run(self, query: str) -> ToolResult:
        hits = retry(
            lambda: DDGS().text(
                query, region=self.region, max_results=self.max_results, backend=self.backend
            )
        )
        if not hits:
            return ToolResult(f"Aucun résultat pour « {query} ».")
        results = [{"title": h["title"], "url": h["href"], "snippet": h["body"]} for h in hits]
        text = "\n".join(
            f"{i}. {r['title']} — {r['snippet']} (source : {r['url']})"
            for i, r in enumerate(results, 1)
        )
        return ToolResult(
            text=f"Résultats pour « {query} » :\n{text}",
            display=Display("results", f"Recherche : {query}", {"results": results}),
        )
