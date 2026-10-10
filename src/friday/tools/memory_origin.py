"""« D'où tu sais que j'habite à Lyon ? », « qui t'a dit ça ? » : la source d'un souvenir (la
phrase dite, la date), combien de fois il a été confirmé, et ce qu'il remplaçait. Le
souvenir est trouvé et la réponse construite par le code."""

from friday.memory.mirror import day
from friday.memory.service import MemoryService
from friday.tools.base import Tool, ToolResult
from friday.tools.memory import MIN_COVERAGE, content_words, coverage
from friday.voice.wake import normalize

# « d'où tu sais que… » : reconnu par le code ; ce qui suit est le souvenir cherché
ASKS = ("d ou tu sais", "comment tu sais", "comment sais tu", "qui t a dit", "pourquoi tu crois",
        "pourquoi tu penses", "d ou tu tiens", "depuis quand tu sais")  # fmt: skip
ASK_WORDS = {"ou", "tu", "sais", "comment", "qui", "dit", "pourquoi", "crois", "penses",
             "tiens", "depuis", "quand", "ca"}  # fmt: skip


def asked_origin(text: str) -> str | None:
    """Ce dont l'utilisateur demande la source, ou None si ce n'est pas la question."""
    words = f" {normalize(text)} "
    for ask in ASKS:
        if (start := words.find(f" {ask} ")) >= 0:
            return words[start + len(ask) + 1 :].strip() or None
    return None


class MemoryOriginTool(Tool):
    name = "memory_origin"
    description = (
        "D'où vient un souvenir (« d'où tu sais que j'habite à Lyon ? », « qui t'a dit ça ? ») : "
        "la phrase et la date, les confirmations, ce qu'il remplaçait."
    )
    parameters = {"about": {"type": "string", "description": "Le souvenir, avec ses mots"}}
    required = ("about",)

    def __init__(self, memory: MemoryService) -> None:
        self.memory = memory

    def label(self, args: dict) -> str:
        return f"🧠 Source : {args.get('about', '')}"

    def run(self, about: str = "") -> ToolResult:
        wanted = content_words(about) - ASK_WORDS
        scored = sorted(((coverage(wanted, m.text), m) for m in self.memory.all()),
                        key=lambda pair: -pair[0])  # fmt: skip
        if not scored or scored[0][0] < MIN_COVERAGE:
            return ToolResult("Dis EXACTEMENT : « Je n'ai aucun souvenir là-dessus. »")
        memory = scored[0][1]
        if memory.said:
            told = f"Tu me l'as dit le {day(memory.created_at)} : « {memory.said} »."
        elif memory.source == "explicit":
            told = f"Tu m'as demandé de le retenir le {day(memory.created_at)}."
        else:
            told = f"Je l'ai noté le {day(memory.created_at)}."
        parts = [told]
        if memory.confirmations > 1:
            parts.append(f"Tu me l'as redit {memory.confirmations - 1} fois depuis.")
        history = self.memory.history(memory.id)
        if history:
            parts.append(f"Avant, je savais : {history[0].text.rstrip('.')} (jusqu'au "
                         f"{day(history[0].updated_at)}).")  # fmt: skip
        return ToolResult(f"Souvenir n°{memory.id} : {memory.text}\n"
                          f"Dis EXACTEMENT : « {' '.join(parts)} »")  # fmt: skip
