"""Mémoire de la conversation en cours."""

from dataclasses import dataclass, field
from typing import Any

# Une fois la réponse donnée, les résultats d'outils sont raccourcis : ils prennent
# beaucoup de place dans la mémoire de travail du modèle.
TOOL_RESULT_KEEP_CHARS = 600


@dataclass
class Conversation:
    """Historique des échanges, limité aux `max_messages` derniers messages."""

    max_messages: int = 30
    messages: list[dict[str, Any]] = field(default_factory=list)

    def add(self, role: str, content: str, **extra: Any) -> None:
        self.messages.append({"role": role, "content": content, **extra})
        overflow = len(self.messages) - self.max_messages
        if overflow > 0:
            del self.messages[:overflow]
        # L'historique doit toujours commencer par une question de l'utilisateur.
        while self.messages and self.messages[0]["role"] != "user":
            self.messages.pop(0)

    def compact_tool_results(self) -> None:
        for message in self.messages:
            content = message["content"]
            if message["role"] == "tool" and len(content) > TOOL_RESULT_KEEP_CHARS:
                message["content"] = content[:TOOL_RESULT_KEEP_CHARS] + " […]"

    def reset(self) -> None:
        self.messages.clear()
