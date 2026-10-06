"""Mémoire de la conversation en cours."""

from dataclasses import dataclass, field
from typing import Any

# Une fois la réponse donnée, les résultats d'outils sont raccourcis : ils prennent
# beaucoup de place dans la mémoire de travail du modèle. Ceux du dernier échange restent
# entiers, pour la question suivante (« approfondis le troisième »).
TOOL_RESULT_KEEP_CHARS = 600


@dataclass
class Conversation:
    """Historique des échanges. Les plus vieux sont résumés (`summary`) quand la mémoire de
    travail se remplit (voir summary.py) ; `max_messages` n'est qu'une limite de secours."""

    max_messages: int = 60
    messages: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""  # résumé du début de la conversation

    def add(self, role: str, content: str, **extra: Any) -> None:
        self.messages.append({"role": role, "content": content, **extra})
        overflow = len(self.messages) - self.max_messages
        if overflow > 0:
            del self.messages[:overflow]
        # L'historique doit toujours commencer par une question de l'utilisateur.
        while self.messages and self.messages[0]["role"] != "user":
            self.messages.pop(0)

    def compact_tool_results(self) -> None:
        """Raccourcit les résultats d'outils, sauf ceux du dernier échange."""
        last_question = max(
            (i for i, m in enumerate(self.messages) if m["role"] == "user"), default=0
        )
        for message in self.messages[:last_question]:
            content = message["content"]
            if message["role"] == "tool" and len(content) > TOOL_RESULT_KEEP_CHARS:
                message["content"] = content[:TOOL_RESULT_KEEP_CHARS] + " […]"

    def old_part(self, keep_exchanges: int) -> list[dict[str, Any]]:
        """Les messages d'avant les `keep_exchanges` dernières questions."""
        questions = [i for i, m in enumerate(self.messages) if m["role"] == "user"]
        if len(questions) <= keep_exchanges:
            return []
        return self.messages[: questions[-keep_exchanges]]

    def fold(self, old: list[dict[str, Any]], summary: str) -> None:
        """Remplace les messages `old` (toujours en tête) par leur résumé."""
        for message in old:
            if self.messages and self.messages[0] is message:
                self.messages.pop(0)
        self.summary = summary

    def reset(self) -> None:
        self.messages.clear()
        self.summary = ""
