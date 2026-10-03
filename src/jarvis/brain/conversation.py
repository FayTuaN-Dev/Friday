"""Mémoire de la conversation en cours."""

from dataclasses import dataclass, field


@dataclass
class Conversation:
    """Historique des échanges, limité aux `max_messages` derniers messages."""

    max_messages: int = 30
    messages: list[dict[str, str]] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        overflow = len(self.messages) - self.max_messages
        if overflow > 0:
            del self.messages[:overflow]
        # Ne jamais commencer l'historique par une réponse orpheline de Jarvis.
        while self.messages and self.messages[0]["role"] != "user":
            self.messages.pop(0)

    def reset(self) -> None:
        self.messages.clear()
