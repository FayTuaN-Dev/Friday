"""La mémoire de Jarvis : retenir, oublier, et retrouver ce qui sert pour une question."""

import logging

from jarvis.memory.embedder import Embedder
from jarvis.memory.store import Memory, MemoryStore

log = logging.getLogger(__name__)

# Au-dessus, deux souvenirs disent la même chose (mesuré : doublons 0,92–0,99, différents ≤ 0,83)
DUPLICATE_SCORE = 0.90
# Tant qu'il y a peu de souvenirs, on les donne tous au LLM : il fait le tri mieux qu'un seuil.
ALL_IF_AT_MOST = 40
TOP_K = 12


class MemoryService:
    def __init__(self, store: MemoryStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder

    def remember(self, text: str, source: str, replaces: int | None = None) -> Memory:
        """Ajoute un souvenir, ou met à jour celui qu'il remplace / qu'il répète."""
        text = text.strip()
        vector = self.embedder.documents([text])[0]
        if replaces is not None and (updated := self.store.update(replaces, text, vector)):
            log.info("Souvenir %d mis à jour : %s", replaces, text)
            return updated
        nearest = self.store.nearest(vector)
        if nearest and nearest[0][1] >= DUPLICATE_SCORE:
            memory = nearest[0][0]
            log.info("Souvenir %d déjà connu, reformulé : %s", memory.id, text)
            return self.store.update(memory.id, text, vector) or memory
        memory = self.store.add(text, source, vector)
        log.info("Nouveau souvenir %d (%s) : %s", memory.id, source, text)
        return memory

    def forget(self, memory_id: int) -> Memory | None:
        memory = self.store.delete(memory_id)
        if memory:
            log.info("Souvenir %d oublié : %s", memory_id, memory.text)
        return memory

    def relevant(self, question: str) -> list[Memory]:
        """Les souvenirs à donner au LLM pour répondre à cette question."""
        if self.store.count() <= ALL_IF_AT_MOST:
            return self.store.all()
        found = self.store.nearest(self.embedder.query(question), TOP_K)
        return sorted((m for m, _ in found), key=lambda m: m.id)

    def all(self) -> list[Memory]:
        return self.store.all()


def format_memories(memories: list[Memory]) -> str:
    """« [3] L'utilisateur est allergique aux arachides. », une ligne par souvenir."""
    return "\n".join(f"[{m.id}] {m.text}" for m in memories)
