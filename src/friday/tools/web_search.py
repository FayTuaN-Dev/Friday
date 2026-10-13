"""Outil : recherche sur internet (DuckDuckGo, gratuit et sans clé)."""

import re

from ddgs import DDGS

from friday.tools.base import Display, Tool, ToolResult, retry
from friday.tools.research import ResearchLog


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Recherche sur internet. À utiliser pour l'actualité, les faits récents, les prix, "
        "les horaires, la météo, ou dès que tu n'es pas sûr d'une information."
    )
    parameters = {"query": {"type": "string", "description": "La recherche, en mots-clés"}}
    required = ("query",)

    def __init__(
        self,
        region: str = "fr-fr",
        max_results: int = 5,
        backend: str = "auto",
        research: ResearchLog | None = None,
    ) -> None:
        self.research = research  # carnet : garde les adresses pour « approfondis le 3 »
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
        if self.research is not None:
            self.research.searched(query, [(r["title"], r["url"]) for r in results])
        text = "\n".join(
            f"{i}. {r['title']} — {r['snippet']} (source : {r['url']})"
            for i, r in enumerate(results, 1)
        )
        return ToolResult(
            text=f"Résultats pour « {query} » :\n{text}",
            display=Display("results", f"Recherche : {query}", {"results": results}),
        )


# Une recherche demandée en toutes lettres : lancée par le code. Constaté : « trouve-moi des
# sites pour faire un planning de stream » → qwen répondait de mémoire, sites inventés compris.
ASKS_WEB = re.compile(
    r"\b(sur (internet|le web|le net|google)|en ligne|sites|un site (pour|qui|ou)"
    r"|site (web|internet)|des liens?|fais une recherche|recherche web)\b"
)
NOT_A_SEARCH = ("ouvre", "lance", "va sur", "affiche", "montre", "mets", "achete", "commande")
FILLER = re.compile(r"^(friday\s*)?((est ce que )?(tu peux|peux tu|pourrais tu|tu pourrais)\s+)?"
                    r"(me\s+)?((re)?cherche[rz]?|trouve[rz]?|donne[rz]?|fais une recherche)?"
                    r"(\s+moi)?\s*(sur (internet|le web|le net|google)\s*)?(pour\s+)?")  # fmt: skip


def search_request(text: str) -> tuple[str, dict] | None:
    """(« web_search », {"query": …}) quand la demande réclame internet en toutes lettres
    (« sur internet », « des sites… ») ; None sinon : qwen garde la main."""
    from friday.brain.thinking import own_words
    from friday.voice.wake import normalize

    plain = normalize(own_words(text))
    if not ASKS_WEB.search(plain) or plain.startswith(NOT_A_SEARCH):
        return None
    query = FILLER.sub("", plain, count=1).strip(" ?!.") or plain
    return ("web_search", {"query": query})
