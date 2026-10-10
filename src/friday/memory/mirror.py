"""Fiche lisible de la mémoire : data/memoire.md, réécrite à chaque changement, rangée par
thème, avec d'où vient chaque fait et ses anciennes versions. Elle se lit seulement :
la modifier ne change pas la mémoire (« retiens que… », « oublie que… » le font)."""

import logging
from pathlib import Path

from friday.memory.categories import CATEGORIES, checked
from friday.memory.store import Memory, MemoryStore

log = logging.getLogger(__name__)

HEADER = """# Ce que Friday sait de toi

> Fiche générée automatiquement (lecture seule) : pour corriger, dis à Friday « retiens
> que… » ou « oublie que… ».
"""


def day(stamp: str) -> str:
    """« 2026-10-03T14:05:00 » → « 03/10/2026 »."""
    return f"{stamp[8:10]}/{stamp[5:7]}/{stamp[:4]}" if len(stamp) >= 10 else stamp


def details(memory: Memory) -> str:
    parts = ["demandé" if memory.source == "explicit" else "déduit", f"le {day(memory.created_at)}"]
    if memory.confirmations > 1:
        parts.append(f"confirmé {memory.confirmations} fois")
    return ", ".join(parts)


def render(store: MemoryStore) -> str:
    memories = store.all()
    lines = [HEADER]
    if not memories:
        return HEADER + "\nRien pour l'instant.\n"
    for category in CATEGORIES:
        group = [m for m in memories if checked(m.category) == category]
        if not group:
            continue
        lines.append(f"\n## {category.capitalize()}\n")
        for memory in group:
            lines.append(f"- {memory.text} _({details(memory)})_")
            if memory.said:
                lines.append(f"  - tu as dit : « {memory.said} »")
            for old in store.history(memory.id):
                lines.append(f"  - avant (jusqu'au {day(old.updated_at)}) : {old.text}")
    return "\n".join(lines) + "\n"


def write(store: MemoryStore, path: Path) -> None:
    try:
        path.write_text(render(store), "utf-8")
    except OSError as error:  # la fiche est un confort : jamais bloquante
        log.warning("Fiche de la mémoire non écrite : %s", error)
