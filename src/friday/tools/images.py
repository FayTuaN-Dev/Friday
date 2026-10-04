"""Outil : chercher des images et les afficher en pop-up."""

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx
from ddgs import DDGS

from friday.tools.base import Display, Tool, ToolResult, retry

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Friday/0.1"}


def download(url: str, timeout: float = 6.0) -> bytes | None:
    try:
        response = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return response.content
    except httpx.HTTPError as e:
        log.debug("Image ignorée %s : %s", url, e)
        return None


class ImageSearchTool(Tool):
    name = "search_images"
    description = (
        "Cherche des images sur internet et les affiche à l'écran de l'utilisateur. "
        "À utiliser quand on te demande de montrer, de faire voir ou à quoi ressemble quelque "
        "chose."
    )
    parameters = {"query": {"type": "string", "description": "Ce qu'il faut montrer"}}
    required = ("query",)

    def __init__(self, region: str = "fr-fr", count: int = 6) -> None:
        self.region = region
        self.count = count

    def label(self, args: dict) -> str:
        return f"🖼️ Images : {args.get('query', '')}"

    def run(self, query: str) -> ToolResult:
        hits = retry(lambda: DDGS().images(query, region=self.region, max_results=self.count * 2))
        # Les miniatures sont légères et rapides à télécharger ; on en demande le double
        # car certaines échouent.
        with ThreadPoolExecutor(max_workers=8) as pool:
            datas = list(pool.map(download, [h["thumbnail"] for h in hits]))
        images = [
            {"title": h["title"], "data": data, "url": h["url"], "image": h["image"]}
            for h, data in zip(hits, datas, strict=True)
            if data
        ][: self.count]
        if not images:
            return ToolResult(f"Aucune image trouvée pour « {query} ».")
        return ToolResult(
            text=(
                f"{len(images)} images de « {query} » sont affichées à l'écran. "
                "Dis-le brièvement, sans les décrire en détail."
            ),
            display=Display("images", query, {"images": images}),
        )
