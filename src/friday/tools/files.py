"""Outils : lire un fichier (PDF, Word, texte), lire et remplir le presse-papier."""

import math

from friday.files.clipboard import ClipboardError, read_clipboard, write_clipboard
from friday.files.readers import Document, UnreadableFile, clean_path, read_document
from friday.tools.base import Display, Tool, ToolResult

PART_CHARS = 6000  # ce que le LLM lit d'un coup (sa mémoire de travail est limitée)
DISPLAY_MAX_CHARS = 60_000


def document_part(document: Document, part: int) -> str:
    """Texte d'une partie du document, avec ce qu'il faut au LLM pour lire la suite."""
    total = max(1, math.ceil(len(document.text) / PART_CHARS))
    part = min(max(1, part), total)
    chunk = document.text[(part - 1) * PART_CHARS : part * PART_CHARS]
    pages = f", {document.pages} pages" if document.pages else ""
    header = f"Contenu de « {document.path.name} » (partie {part}/{total}{pages}) :\n"
    if part < total:
        chunk += (
            f"\n\n[Suite non lue : parties {part + 1} à {total}. Si la réponse n'est pas "
            f"ci-dessus, rappelle read_file avec part={part + 1}.]"
        )
    return header + chunk


def file_display(document: Document) -> Display:
    return Display(
        "article",
        document.path.name,
        {"path": str(document.path), "text": document.text[:DISPLAY_MAX_CHARS]},
    )


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Lit un fichier de l'ordinateur (PDF, Word .docx, texte, code) pour le résumer, "
        "le traduire ou répondre à une question dessus. Les longs documents se lisent par "
        "parties (part=1, 2…)."
    )
    parameters = {
        "path": {"type": "string", "description": "Chemin complet du fichier"},
        "part": {"type": "integer", "description": "Partie à lire (1 par défaut)"},
    }
    required = ("path",)

    def label(self, args: dict) -> str:
        name = clean_path(args.get("path", "")).name
        part = args.get("part") or 1
        return f"📄 Lecture : {name}" + (f" (partie {part})" if part > 1 else "")

    def run(self, path: str, part: int | None = None) -> ToolResult:
        try:
            document = read_document(clean_path(path))
        except UnreadableFile as error:
            return ToolResult(f"{error} Préviens l'utilisateur.")
        part = int(part or 1)
        display = file_display(document) if part == 1 else None  # le document s'ouvre une fois
        return ToolResult(document_part(document, part), display)


class ReadClipboardTool(Tool):
    name = "read_clipboard"
    description = (
        "Lit le contenu du presse-papier : le texte (ou le fichier) que l'utilisateur a copié. "
        "À appeler AVANT de corriger, traduire, résumer ou expliquer « ce que j'ai copié »."
    )
    parameters: dict = {}

    def label(self, args: dict) -> str:
        return "📋 Presse-papier"

    def run(self) -> ToolResult:
        try:
            content = read_clipboard()
        except ClipboardError as error:
            return ToolResult(f"{error} Préviens l'utilisateur.")
        if content.files:  # fichier(s) copié(s) dans l'explorateur : on lit le premier
            others = content.files[1:]
            try:
                document = read_document(clean_path(content.files[0]))
            except UnreadableFile as error:
                return ToolResult(f"Fichier copié : {error} Préviens l'utilisateur.")
            note = f"\n(Autres fichiers copiés, non lus : {', '.join(others)})" if others else ""
            return ToolResult(document_part(document, 1) + note, file_display(document))
        text = content.text.strip()
        if not text:
            return ToolResult("Le presse-papier est vide (ou contient une image). Dis-le.")
        if len(text) > PART_CHARS:
            text = text[:PART_CHARS] + "\n[… texte copié coupé : trop long pour tout lire]"
        return ToolResult(f"Texte copié par l'utilisateur :\n{text}")


class CopyToClipboardTool(Tool):
    name = "copy_to_clipboard"
    description = (
        "Copie un texte dans le presse-papier (un texte corrigé, traduit, rédigé…), pour que "
        "l'utilisateur le colle où il veut. Quand il dit « copie-le », « mets-le dans le "
        "presse-papier », ou après avoir corrigé un texte qu'il avait copié."
    )
    parameters = {"text": {"type": "string", "description": "Le texte complet à copier"}}
    required = ("text",)

    def label(self, args: dict) -> str:
        return "📋 Copié dans le presse-papier"

    def run(self, text: str) -> ToolResult:
        try:
            write_clipboard(text)
        except ClipboardError as error:
            return ToolResult(f"{error} Préviens l'utilisateur.")
        return ToolResult(
            "Copié dans le presse-papier. Dis-le en une phrase ; un texte court (traduction, "
            "phrase corrigée) peut aussi être dit, un long texte non."
        )
