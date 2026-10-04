"""Outils : notes et listes (courses, tâches…)."""

from jarvis.agenda.store import AgendaStore
from jarvis.tools.base import Display, Tool, ToolResult
from jarvis.voice.wake import normalize

DEFAULT_LIST = "notes"
FILLER_WORDS = {"liste", "de", "des", "la", "ma", "mes", "du", "le", "les", "a"}


def list_key(name: str | None) -> str:
    """« Liste de courses », « mes courses » → « courses »."""
    words = [w for w in normalize(name or DEFAULT_LIST).split() if w not in FILLER_WORDS]
    return " ".join(words) or DEFAULT_LIST


class AddNoteTool(Tool):
    name = "add_note"
    description = (
        "Ajoute un élément à une liste (courses, tâches, idées…) ou une note. Un appel par "
        "élément : « ajoute du lait et des œufs » = deux appels."
    )
    parameters = {
        "text": {"type": "string", "description": "L'élément ou la note"},
        "list": {"type": "string", "description": "La liste : courses, tâches… (vide = notes)"},
    }
    required = ("text",)

    def __init__(self, store: AgendaStore) -> None:
        self.store = store

    def label(self, args: dict) -> str:
        return f"📝 {list_key(args.get('list')).capitalize()} : {args.get('text', '')}"

    def run(self, text: str, list: str | None = None) -> ToolResult:  # noqa: A002
        note = self.store.add_note(list_key(list), text.strip())
        return ToolResult(f"Ajouté à « {note.list} » (n°{note.id}) : {note.text}.")


class ListNotesTool(Tool):
    name = "list_notes"
    description = "Affiche le contenu d'une liste (courses, tâches…) ou toutes les notes."
    parameters = {"list": {"type": "string", "description": "La liste (vide = tout)"}}

    def __init__(self, store: AgendaStore) -> None:
        self.store = store

    def label(self, args: dict) -> str:
        return f"📝 Liste : {args.get('list') or 'tout'}"

    def run(self, list: str | None = None) -> ToolResult:  # noqa: A002
        key = list_key(list) if list else None
        notes = self.store.notes(key)
        if not notes:
            known = ", ".join(self.store.lists()) or "aucune"
            return ToolResult(
                f"La liste « {key or 'notes'} » est vide. Listes existantes : {known}."
            )
        lines = "\n".join(f"[{n.id}] ({n.list}) {n.text}" for n in notes)
        items = [{"text": n.text, "meta": f"n°{n.id} · {n.list}"} for n in notes]
        title = f"Liste : {key}" if key else "Toutes les notes"
        return ToolResult(
            f"Contenu (affiché à l'écran) :\n{lines}",
            Display("items", title, {"icon": "📝", "items": items}),
        )


class RemoveNoteTool(Tool):
    name = "remove_note"
    description = (
        "Retire un élément d'une liste, par son numéro (voir list_notes) : quand c'est fait, "
        "acheté, ou que l'utilisateur demande de l'enlever."
    )
    parameters = {"note_id": {"type": "integer", "description": "Numéro de l'élément"}}
    required = ("note_id",)

    def __init__(self, store: AgendaStore) -> None:
        self.store = store

    def label(self, args: dict) -> str:
        return f"📝 Retrait n°{args.get('note_id')}"

    def run(self, note_id: int) -> ToolResult:
        note = self.store.remove_note(int(note_id))
        if note is None:
            return ToolResult(f"Pas d'élément n°{note_id}.")
        return ToolResult(f"Retiré de « {note.list} » : {note.text}.")
