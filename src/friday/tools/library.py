"""Outils : chercher dans la bibliothèque (PDF, livres, cours de l'utilisateur), la lister,
la mettre à jour."""

from friday.library.library import Library
from friday.library.store import Hit
from friday.tools.base import Display, Tool, ToolResult

SNIPPET_CHARS = 220  # extrait montré dans le pop-up


def where(hit: Hit) -> str:
    return f"{hit.document}, page {hit.page}" if hit.page else hit.document


class SearchLibraryTool(Tool):
    name = "search_library"
    description = (
        "Cherche dans la bibliothèque de l'utilisateur (ses PDF, livres, cours et notes "
        "déposés dans Friday) les passages qui répondent à une question. À utiliser AVANT "
        "internet quand il parle de « mes livres », « mes documents », « ma bibliothèque », "
        "ou d'un sujet qu'il y a rangé. Réponds à partir des passages et cite la source."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "La question ou les mots-clés (« qu'est-ce qu'un pip », "
            "« gestion du risque »)",
        }
    }
    required = ("query",)

    def __init__(self, library: Library) -> None:
        self.library = library
        self.timeout = 20

    def label(self, args: dict) -> str:
        return f"📚 Bibliothèque : {args.get('query', '')}"

    def run(self, query: str) -> ToolResult:
        if not self.library.store.documents():
            return ToolResult(
                "La bibliothèque est vide : l'utilisateur peut y déposer des PDF, livres ou "
                "notes (Réglages → Bibliothèque)."
            )
        hits = self.library.search(query)
        if not hits:
            return ToolResult(f"Rien de pertinent dans la bibliothèque pour « {query} ».")
        text = "\n\n".join(f"[{where(h)}]\n{h.text}" for h in hits)
        items = [
            {"name": where(h), "path": h.path, "where": h.text[:SNIPPET_CHARS] + "…", "meta": ""}
            for h in hits
        ]
        return ToolResult(
            text=f"Passages de la bibliothèque pour « {query} » :\n\n{text}",
            display=Display("files", f"Bibliothèque : {query}", {"files": items}),
        )


class ListLibraryTool(Tool):
    name = "list_library"
    description = "Liste les documents de la bibliothèque (« qu'y a-t-il dans ma bibliothèque ? »)."
    parameters = {}

    def __init__(self, library: Library) -> None:
        self.library = library

    def run(self) -> ToolResult:
        documents = self.library.store.documents()
        if not documents:
            return ToolResult("La bibliothèque est vide.")
        lines = [f"- {d.name}" + (f" ({d.pages} pages)" if d.pages else "") for d in documents]
        pending = (
            f" Indexation en cours : {self.library.indexing}." if self.library.indexing else ""
        )
        return ToolResult(f"{len(documents)} document(s) :\n" + "\n".join(lines) + pending)


class UpdateLibraryTool(Tool):
    name = "update_library"
    description = (
        "Met à jour la bibliothèque après l'ajout ou le retrait de fichiers dans son dossier "
        "(« mets à jour ma bibliothèque », « j'ai ajouté un livre »)."
    )
    parameters = {}

    def __init__(self, library: Library) -> None:
        self.library = library
        self.timeout = 600  # un gros livre peut prendre une minute ou deux

    def run(self) -> ToolResult:
        report = self.library.sync()
        parts = []
        if report["added"]:
            parts.append("ajoutés ou mis à jour : " + ", ".join(report["added"]))
        if report["removed"]:
            parts.append("retirés : " + ", ".join(report["removed"]))
        if report["failed"]:
            parts.append("illisibles : " + " ; ".join(report["failed"]))
        return ToolResult(
            "Bibliothèque à jour. " + (" ; ".join(parts) if parts else "Rien de nouveau.")
        )
