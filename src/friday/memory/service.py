"""La mémoire de Friday : retenir (renforcer ce qui est redit, remplacer ce qui est corrigé
en gardant l'historique), oublier, et retrouver ce qui sert pour une question."""

import logging
from pathlib import Path

from friday.memory.categories import checked
from friday.memory.embedder import Embedder
from friday.memory.store import Memory, MemoryStore

log = logging.getLogger(__name__)

# Au-dessus, deux souvenirs disent la même chose (mesuré : doublons 0,92–0,99, différents ≤ 0,83)
DUPLICATE_SCORE = 0.90
# Tant qu'il y a peu de souvenirs, on les donne tous au LLM : il fait le tri mieux qu'un seuil.
ALL_IF_AT_MOST = 40
TOP_K = 12


class MemoryService:
    def __init__(self, store: MemoryStore, embedder: Embedder, mirror: Path | None = None):
        """`mirror` : la fiche lisible (data/memoire.md), réécrite à chaque changement."""
        self.store = store
        self.embedder = embedder
        self.mirror = mirror
        self._write_mirror()

    def remember(self, text: str, source: str, replaces: int | None = None,
                 category: str = "", said: str = "") -> Memory:  # fmt: skip
        """Ajoute un souvenir ; s'il en corrige un (`replaces`), l'ancien passe dans
        l'historique ; s'il en répète un, celui-ci est renforcé."""
        text, said = text.strip(), " ".join(said.split())[:300]
        vector = self.embedder.documents([text])[0]
        old = self.store.get(replaces) if replaces is not None else None
        if old is not None and old.status == "active":
            memory = self.store.add(text, source, vector, checked(category or old.category),
                                    said)  # fmt: skip
            self.store.replace(old.id, memory.id)
            log.info("Souvenir %d remplacé par %d : %s", old.id, memory.id, text)
            return self._changed(memory)
        nearest = self.store.nearest(vector)
        if nearest and nearest[0][1] >= DUPLICATE_SCORE:
            known = nearest[0][0]
            memory = self.store.confirm(known.id, text, vector) or known
            log.info("Souvenir %d confirmé (%d fois) : %s", known.id, memory.confirmations, text)
            return self._changed(memory)
        memory = self.store.add(text, source, vector, checked(category), said)
        log.info("Nouveau souvenir %d (%s, %s) : %s", memory.id, source, memory.category, text)
        return self._changed(memory)

    def forget(self, memory_id: int) -> Memory | None:
        memory = self.store.delete(memory_id)
        if memory:
            log.info("Souvenir %d oublié : %s", memory_id, memory.text)
            self._write_mirror()
        return memory

    def history(self, memory_id: int) -> list[Memory]:
        return self.store.history(memory_id)

    def set_category(self, memory_id: int, category: str) -> None:
        self.store.set_category(memory_id, checked(category))
        self._write_mirror()

    def relevant(self, question: str) -> list[Memory]:
        """Les souvenirs à donner au LLM pour répondre à cette question."""
        if self.store.count() <= ALL_IF_AT_MOST:
            return self.store.all()
        found = self.store.nearest(self.embedder.query(question), TOP_K)
        return sorted((m for m, _ in found), key=lambda m: m.id)

    def all(self) -> list[Memory]:
        return self.store.all()

    def _changed(self, memory: Memory) -> Memory:
        self._write_mirror()
        return memory

    def _write_mirror(self) -> None:
        if self.mirror is not None:
            from friday.memory.mirror import write

            write(self.store, self.mirror)


def format_memories(memories: list[Memory]) -> str:
    """« [3] L'utilisateur est allergique aux arachides. », une ligne par souvenir."""
    return "\n".join(f"[{m.id}] {m.text}" for m in memories)
