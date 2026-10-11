"""Outil : ouvrir la fiche mémoire (data/memoire.md), la copie lisible des souvenirs.

Constaté : « ouvre data/memoire.md » → qwen ouvrait le Bloc-notes vide et disait ne pas avoir
accès aux fichiers (le dossier data n'est pas dans ceux qu'il peut ouvrir). La demande est
reconnue par le code et le fichier ouvert dans l'appli habituelle des .md.
"""

import os
from collections.abc import Callable

from friday.memory.service import MemoryService
from friday.tools.base import Tool, ToolResult
from friday.voice.wake import normalize

ASKS = ("fiche memoire", "fiche de memoire", "memoire md", "fichier memoire",
        "fichier de memoire", "fichier de ta memoire", "fiche de ta memoire")  # fmt: skip
VERBS = ("ouvre", "montre", "affiche", "lance", "fais moi voir")


def asks_sheet(text: str) -> bool:
    """« ouvre ta fiche mémoire », « ouvre data/memoire.md », « montre le fichier mémoire »."""
    padded = f" {normalize(text)} "
    return any(f" {v}" in padded for v in VERBS) and any(f" {a}" in padded for a in ASKS)


class OpenMemorySheetTool(Tool):
    name = "open_memory_sheet"
    description = (
        "Ouvre la fiche mémoire (data/memoire.md) : tous les souvenirs, classés par thèmes, "
        "à lire ou vérifier (« ouvre ta fiche mémoire »)."
    )
    parameters = {}

    def __init__(self, memory: MemoryService, open_file: Callable[[str], None] = os.startfile):
        self.memory, self.open_file = memory, open_file

    def label(self, args: dict) -> str:
        return "🧠 Fiche mémoire"

    def run(self) -> ToolResult:
        sheet = self.memory.mirror
        if sheet is None or not sheet.exists():
            return ToolResult("Dis EXACTEMENT : « Ma fiche mémoire n'existe pas encore : je ne "
                              "me souviens de rien pour l'instant. »")  # fmt: skip
        self.open_file(str(sheet))
        count = self.memory.store.count()
        many = f"{count} souvenirs, classés" if count > 1 else f"{count} souvenir, classé"
        return ToolResult(f"Dis EXACTEMENT : « J'ouvre ma fiche mémoire : {many} par thèmes. »")
