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


class ForgetTool(Tool):
    name = "forget_memory"
    description = (
        "Efface un souvenir. À utiliser quand l'utilisateur demande d'oublier quelque chose : "
        "donne le numéro du souvenir, celui entre crochets dans ta mémoire."
    )
    parameters = {"memory_id": {"type": "integer", "description": "Numéro du souvenir"}}
    required = ("memory_id",)

    def __init__(self, memory: MemoryService) -> None:
        self.memory = memory

    def label(self, args: dict) -> str:
        return f"🧠 Oubli du souvenir n°{args.get('memory_id', '?')}"

    def run(self, memory_id: int) -> ToolResult:
        forgotten = self.memory.forget(int(memory_id))
        if forgotten is None:
            return ToolResult(f"Il n'y a pas de souvenir n°{memory_id}.")
        return ToolResult(f"C'est oublié : {forgotten.text}")


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
