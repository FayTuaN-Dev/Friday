"""Outil : ouvrir un site dans le navigateur."""

import webbrowser

from jarvis.tools.base import Tool, ToolResult


class OpenWebsiteTool(Tool):
    name = "open_website"
    description = (
        "Ouvre un site web dans le navigateur de l'utilisateur (YouTube, Gmail, Netflix, un "
        "lien donné…). Donne l'adresse complète, par exemple https://www.youtube.com."
    )
    parameters = {"url": {"type": "string", "description": "Adresse du site"}}
    required = ("url",)

    def __init__(self, open_url=webbrowser.open) -> None:
        self.open_url = open_url

    def label(self, args: dict) -> str:
        return f"🌐 Ouverture : {args.get('url', '')}"

    def run(self, url: str) -> ToolResult:
        url = url.strip()
        if " " in url or "." not in url:
            return ToolResult(f"« {url} » n'est pas une adresse de site.")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        self.open_url(url)
        return ToolResult(f"Site ouvert : {url}")
