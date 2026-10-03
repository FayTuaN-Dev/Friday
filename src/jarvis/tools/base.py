"""Socle des outils : chaque outil est un plugin que le LLM peut décider d'appeler."""

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


def retry[T](fn: Callable[[], T], attempts: int = 2, delay: float = 0.5) -> T:
    """Relance une requête réseau qui échoue (les services web ont des ratés passagers)."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == attempts:
                raise
            log.warning("Tentative %d échouée (%s), nouvel essai", attempt, e)
            time.sleep(delay)
    raise AssertionError("inatteignable")


@dataclass
class Display:
    """Contenu à montrer à l'écran (pop-up)."""

    kind: str  # "results", "article" ou "images"
    title: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    text: str  # ce que le LLM lit pour formuler sa réponse
    display: Display | None = None  # ce que l'utilisateur voit


class Tool(ABC):
    name: str
    description: str  # lue par le LLM pour savoir quand utiliser l'outil
    parameters: dict[str, dict[str, Any]]  # propriétés JSON Schema
    required: tuple[str, ...] = ()

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolResult: ...

    def label(self, args: dict[str, Any]) -> str:
        """Phrase courte affichée pendant l'exécution (ex. « Recherche : météo Lyon »)."""
        return self.name

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.required),
                },
            },
        }


class ToolBox:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {t.name: t for t in tools}

    def __bool__(self) -> bool:
        return bool(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def label(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        return tool.label(args) if tool else name

    def run(self, name: str, args: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(f"Erreur : l'outil « {name} » n'existe pas.")
        try:
            return tool.run(**args)
        except Exception as e:
            log.exception("Échec de l'outil %s(%s)", name, args)
            return ToolResult(f"Erreur pendant « {name} » : {e}. Préviens l'utilisateur.")
