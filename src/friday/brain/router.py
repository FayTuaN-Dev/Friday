"""Aiguillage : quelles compétences donner au modèle pour cette demande ?

1. Mots-clés (instantané, sans erreur sur les cas courants) ;
2. sinon, le sens de la phrase, comparé à des exemples (embeddings, si disponibles) ;
3. plus les compétences de l'échange précédent (« supprime-le », « réponds-lui »).
Si l'aiguillage rate quand même, le modèle peut charger une compétence (outil load_skill).
"""

import logging
from collections.abc import Callable

import numpy as np

from friday.brain.skills import Skill
from friday.voice.wake import normalize

log = logging.getLogger(__name__)

SIMILARITY = 0.55  # ressemblance minimale avec un exemple (réglée sur des phrases réelles)
MAX_BY_MEANING = 2


class SkillRouter:
    def __init__(
        self,
        skills: tuple[Skill, ...],
        embed_query: Callable[[str], np.ndarray] | None = None,
        embed_documents: Callable[[list[str]], np.ndarray] | None = None,
    ) -> None:
        self.skills = skills
        self._embed_query = embed_query
        self._embed_documents = embed_documents
        self._examples: list[tuple[Skill, np.ndarray]] | None = None

    def choose(self, text: str) -> set[str]:
        """Noms des compétences que cette phrase demande (sans celles de l'échange précédent,
        que le cerveau ajoute lui-même)."""
        padded = f" {normalize(text)} "
        chosen = {s.name for s in self.skills if any(f" {k}" in padded for k in s.keywords)}
        return chosen or self._by_meaning(text)

    def _by_meaning(self, text: str) -> set[str]:
        if self._embed_query is None or self._embed_documents is None or not text.strip():
            return set()
        try:
            if self._examples is None:
                pairs = [(s, e) for s in self.skills for e in s.examples]
                vectors = self._embed_documents([e for _, e in pairs])
                self._examples = [(s, v) for (s, _), v in zip(pairs, vectors, strict=True)]
            query = self._embed_query(text)
        except Exception as error:  # modèle d'embeddings indisponible : pas grave
            log.warning("Aiguillage par le sens indisponible : %s", error)
            return set()
        best: dict[str, float] = {}
        for skill, vector in self._examples:
            score = float(np.dot(query, vector) / (np.linalg.norm(query) * np.linalg.norm(vector)))
            best[skill.name] = max(best.get(skill.name, -1.0), score)
        ranked = sorted(best.items(), key=lambda item: -item[1])
        return {name for name, score in ranked[:MAX_BY_MEANING] if score >= SIMILARITY}
