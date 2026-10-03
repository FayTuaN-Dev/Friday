"""Ce que le cerveau produit pendant une réponse, en plus du texte."""

from dataclasses import dataclass
from typing import Any

from jarvis.tools.base import ToolResult


@dataclass
class ToolStarted:
    name: str
    args: dict[str, Any]
    label: str  # ex. « 🔎 Recherche : météo Lyon »


@dataclass
class ToolFinished:
    name: str
    result: ToolResult


# Une réponse est un flux de morceaux de texte (str) entrecoupés d'événements d'outils.
BrainEvent = str | ToolStarted | ToolFinished
