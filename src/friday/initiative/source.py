"""Ce qu'une initiative propose au veilleur : la phrase à dire et les sujets qu'elle couvre (le
garde-fou s'en sert pour ne jamais redire la même chose)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Candidate:
    keys: tuple[str, ...]  # « depart:… », « mail:… » (plusieurs : mails réunis en une phrase)
    text: str  # consigne pour Friday (« Dis EXACTEMENT : « … » »)


class Source(Protocol):
    def candidates(self, now: datetime, said: Callable[[str], bool]) -> list[Candidate]:
        """Ce qu'il y aurait d'utile à dire maintenant ; `said` : ce sujet a-t-il déjà été dit ?"""
        ...
