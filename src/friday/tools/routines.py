"""Outils des routines (J5) : en créer (« tous les lundis à 8 h, trie mes mails »), les
lister, en supprimer. Jours et heure lus par le code ; les phrases à dire aussi."""

from datetime import datetime

from friday.agenda.routines import RoutineStore, describe, parse_days
from friday.tools.base import Tool, ToolResult
from friday.tools.memory import content_words

ASIDE = {"routine", "celle", "tous", "jours", "chaque"}


def overlap(wanted: set[str], request: str) -> float:
    """Part des mots cherchés présents dans la demande (même début : « mail » = « mails »)."""
    stems = {w[:4] for w in content_words(request)}
    return sum(w[:4] in stems for w in wanted) / len(wanted) if wanted else 0.0


class AddRoutineTool(Tool):
    name = "add_routine"
    description = (
        "Programme une ROUTINE : une demande que Friday fera elle-même, régulièrement, à heure "
        "fixe (« tous les jours à 7 h, fais-moi mon briefing », « le lundi à 8 h, trie mes "
        "mails »). Pas pour un rappel unique (set_reminder)."
    )
    parameters = {
        "request": {"type": "string",
                    "description": "Ce que Friday fera, avec les mots de l'utilisateur, sans "
                                   "l'heure ni les jours (« trie mes mails »)"},
        "time": {"type": "string", "description": "L'heure, « 07:30 »"},
        "days": {"type": "string",
                 "description": "Les jours tels que dits : « tous les jours », « en semaine », "
                                "« le week-end », « lundi et jeudi »"},
    }  # fmt: skip
    required = ("request", "time")

    def __init__(self, store: RoutineStore, clock=datetime.now) -> None:
        self.store, self.clock = store, clock

    def label(self, args: dict) -> str:
        return f"🔁 Routine : {args.get('request', '')}"

    def run(self, request: str, time: str, days: str = "") -> ToolResult:
        if not request.strip():
            return ToolResult("Demande l'action à programmer.")
        try:
            routine = self.store.add(request, time, parse_days(days), self.clock())
        except ValueError as error:
            return ToolResult(f"Routine non créée : {error}. Demande l'heure à l'utilisateur.")
        return ToolResult(f"Dis EXACTEMENT : « C'est programmé : {describe(routine)}. »")


class ListRoutinesTool(Tool):
    name = "list_routines"
    description = "Liste les routines programmées (« quelles sont mes routines ? »)."
    parameters = {}

    def __init__(self, store: RoutineStore) -> None:
        self.store = store

    def label(self, args: dict) -> str:
        return "🔁 Routines"

    def run(self) -> ToolResult:
        routines = self.store.all()
        if not routines:
            return ToolResult("Dis EXACTEMENT : « Aucune routine programmée. »")
        listing = " ; ".join(f"{n}) {describe(r)}" for n, r in enumerate(routines, 1))
        return ToolResult(f"Dis EXACTEMENT : « Tes routines : {listing}. »")


class RemoveRoutineTool(Tool):
    name = "remove_routine"
    description = (
        "Supprime une routine programmée : « about » = ce qu'elle fait, avec les mots de "
        "l'utilisateur (« celle des mails »), ou « number » = son numéro dans la liste."
    )
    parameters = {
        "about": {"type": "string", "description": "Ce que fait la routine"},
        "number": {"type": "integer", "description": "Son numéro dans la liste"},
    }

    def __init__(self, store: RoutineStore) -> None:
        self.store = store

    def label(self, args: dict) -> str:
        return f"🔁 Suppression : {args.get('about') or args.get('number', '?')}"

    def run(self, about: str = "", number: int | None = None) -> ToolResult:
        routines = self.store.all()
        if number is not None and 1 <= int(number) <= len(routines):
            target = routines[int(number) - 1]
        else:
            wanted = content_words(about) - ASIDE
            scored = sorted(((overlap(wanted, r.request), r) for r in routines),
                            key=lambda pair: -pair[0])  # fmt: skip
            best = [r for score, r in scored if score >= 0.5 and score == scored[0][0]]
            if len(best) != 1:
                return ToolResult("Rien supprimé : précise laquelle (son numéro dans la liste).")
            target = best[0]
        self.store.remove(target.id)
        return ToolResult(f"Dis EXACTEMENT : « Routine supprimée : {describe(target)}. »")
