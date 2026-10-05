"""Outils de mémoire : retenir, oublier, et montrer ce que Friday sait de l'utilisateur."""

from friday.memory.service import MemoryService
from friday.tools.base import Display, Tool, ToolResult


class RememberTool(Tool):
    name = "remember"
    description = (
        "Mémorise durablement une information sur l'utilisateur. À utiliser quand il te "
        "demande de retenir quelque chose, ou quand il corrige une information que tu as déjà "
        "(déménagement, nouveau travail…) : indique alors le souvenir remplacé."
    )
    parameters = {
        "fact": {
            "type": "string",
            "description": "Le fait, en une phrase à la 3e personne : « L'utilisateur … »",
        },
        "replaces": {
            "type": "integer",
            "description": "Numéro du souvenir que ce fait remplace (s'il le contredit)",
        },
    }
    required = ("fact",)

    def __init__(self, memory: MemoryService) -> None:
        self.memory = memory

    def label(self, args: dict) -> str:
        return f"🧠 Mémorisation : {args.get('fact', '')}"

    def run(self, fact: str, replaces: int | None = None) -> ToolResult:
        memory = self.memory.remember(fact, "explicit", int(replaces) if replaces else None)
        return ToolResult(f"C'est mémorisé (souvenir n°{memory.id}) : {memory.text}")


# Mots qui ne disent rien du souvenir visé (« oublie le fait que je … »)
IGNORED = {
    "oublie", "oublier", "le", "la", "les", "l", "de", "du", "des", "que", "qu", "fait", "je",
    "j", "me", "m", "moi", "mon", "ma", "mes", "suis", "ai", "utilisateur", "souvenir", "un",
    "une", "a", "est", "s", "c", "ce", "n", "pas", "plus", "numero",
}  # fmt: skip


MIN_COVERAGE = 0.6  # part des mots de la demande à retrouver dans le souvenir


def content_words(text: str) -> set[str]:
    from friday.voice.wake import normalize

    return {w for w in normalize(text).split() if w not in IGNORED and len(w) > 1}


def coverage(wanted: set[str], memory_text: str) -> float:
    """Part des mots demandés présents dans le souvenir (« vis » ≈ « vit »)."""
    from difflib import SequenceMatcher

    if not wanted:
        return 0.0
    words = content_words(memory_text)

    def close(a: str, b: str) -> bool:
        return a == b or SequenceMatcher(None, a, b).ratio() >= 0.66

    found = sum(1 for w in wanted if any(close(w, m) for m in words))
    return found / len(wanted)


class ForgetTool(Tool):
    name = "forget_memory"
    description = (
        "Efface un souvenir quand l'utilisateur demande d'oublier quelque chose. « about » : "
        "ce qu'il faut oublier, avec ses mots (« je m'appelle Rollercoin ») ; « memory_id » : "
        "le numéro entre crochets s'il est connu. Friday vérifie que le souvenir correspond."
    )
    parameters = {
        "about": {"type": "string", "description": "Ce qu'il faut oublier, tel que dit"},
        "memory_id": {"type": "integer", "description": "Numéro du souvenir, si connu"},
    }
    required = ("about",)

    def __init__(self, memory: MemoryService) -> None:
        self.memory = memory

    def label(self, args: dict) -> str:
        return f"🧠 Oubli : {args.get('about') or args.get('memory_id', '?')}"

    def run(self, about: str = "", memory_id: int | None = None) -> ToolResult:
        """Le modèle choisit parfois un numéro au hasard (liste périmée) : on n'efface que le
        souvenir dont le texte correspond à ce que l'utilisateur veut oublier."""
        wanted = content_words(about)
        memories = self.memory.all()
        by_id = {m.id: m for m in memories}
        if memory_id is not None and int(memory_id) in by_id:
            target = by_id[int(memory_id)]
            if not wanted or coverage(wanted, target.text) >= MIN_COVERAGE:
                return self._forget(target.id)
        scored = sorted(((coverage(wanted, m.text), m) for m in memories), key=lambda p: -p[0])
        best = [m for score, m in scored if score >= MIN_COVERAGE and score == scored[0][0]]
        if len(best) == 1:
            return self._forget(best[0].id)
        if not best:
            return ToolResult(
                f"Rien effacé : aucun souvenir ne parle de « {about} » (peut-être déjà oublié). "
                "Dis-le à l'utilisateur."
            )
        options = "; ".join(f"[{m.id}] {m.text}" for m in best)
        return ToolResult(
            f"Rien effacé : plusieurs souvenirs possibles ({options}). Demande lequel."
        )

    def _forget(self, memory_id: int) -> ToolResult:
        forgotten = self.memory.forget(memory_id)
        return ToolResult(f"C'est oublié : {forgotten.text}" if forgotten else "Rien effacé.")


class ListMemoriesTool(Tool):
    name = "list_memories"
    description = (
        "Affiche à l'écran tout ce que tu as mémorisé sur l'utilisateur. À utiliser quand il "
        "demande ce que tu sais sur lui ou ce dont tu te souviens."
    )
    parameters = {}

    def __init__(self, memory: MemoryService) -> None:
        self.memory = memory

    def label(self, args: dict) -> str:
        return "🧠 Souvenirs"

    def run(self) -> ToolResult:
        memories = self.memory.all()
        if not memories:
            return ToolResult("Ta mémoire est vide pour l'instant.")
        items = [
            {"id": m.id, "text": m.text, "date": m.updated_at[:10], "source": m.source}
            for m in memories
        ]
        listing = "\n".join(f"- {m.text}" for m in memories)
        return ToolResult(
            text=(
                f"Tes {len(memories)} souvenirs (affichés à l'écran) :\n{listing}\n"
                "Résume-les en une ou deux phrases, sans rien ajouter qui n'y figure pas."
            ),
            display=Display("memories", "Ce que je sais sur vous", {"memories": items}),
        )
