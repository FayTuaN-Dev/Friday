"""Les outils et consignes donnés au modèle pour UNE demande : le noyau, les compétences
choisies par l'aiguillage, celles de l'échange précédent, et celles que le modèle charge
lui-même (load_skill) s'il lui en manque une."""

from typing import Any

from friday.brain.router import SkillRouter
from friday.brain.skills import BY_NAME, CORE_GUIDE, CORE_TOOLS, SKILLS
from friday.tools.base import ToolBox

LOAD_SKILL = "load_skill"


class Toolset:
    def __init__(self, toolbox: ToolBox, router: SkillRouter | None = None) -> None:
        self.toolbox = toolbox
        available = set(toolbox.names())
        self.skills = [s for s in SKILLS if available & set(s.tools)]
        skill_tools = {t for s in SKILLS for t in s.tools}
        self._always = (set(CORE_TOOLS) | (available - skill_tools)) & available
        self.router = router
        self.active: set[str] = {s.name for s in self.skills}  # sans aiguillage : tout
        self._fresh: set[str] = set()
        self._previous: set[str] = set()

    def start(self, user_text: str) -> None:
        """Début d'une demande : choisit les compétences actives."""
        if self.router is None:
            return
        self._fresh = self.router.choose(user_text) & {s.name for s in self.skills}
        self.active = self._fresh | self._previous

    def load(self, name: str) -> str:
        if name not in BY_NAME or BY_NAME[name] not in self.skills:
            return f"Compétence inconnue : « {name} »."
        self.active.add(name)
        self._fresh.add(name)
        return f"Compétence « {name} » chargée : ses outils sont maintenant disponibles."

    def finish(self) -> None:
        """Fin d'une demande : ce qui a servi reste actif pour l'échange suivant
        (« supprime-le », « réponds-lui »), mais pas plus longtemps."""
        if self.router is not None:
            self._previous = set(self._fresh)

    def tool_names(self) -> set[str]:
        names = set(self._always)
        for skill in self.skills:
            if skill.name in self.active:
                names |= set(skill.tools)
        return names

    def schemas(self) -> list[dict[str, Any]]:
        schemas = self.toolbox.schemas(self.tool_names())
        inactive = [s for s in self.skills if s.name not in self.active]
        if self.router is not None and inactive:
            catalog = " ; ".join(f"{s.name} : {s.label}" for s in inactive)
            schemas.append({
                "type": "function",
                "function": {
                    "name": LOAD_SKILL,
                    "description": "Charge une compétence qui te manque pour répondre (ses outils "
                    f"deviennent disponibles). Disponibles : {catalog}.",
                    "parameters": {
                        "type": "object",
                        "properties": {"skill": {"type": "string",
                                                 "enum": [s.name for s in inactive]}},
                        "required": ["skill"],
                    },
                },
            })  # fmt: skip
        return schemas

    def guides(self) -> str:
        parts = [CORE_GUIDE] + [s.guide for s in self.skills if s.name in self.active]
        inactive = [s for s in self.skills if s.name not in self.active]
        if self.router is not None and inactive:
            others = ", ".join(s.label for s in inactive)
            parts.append(
                f"- Tu sais aussi faire (outil load_skill pour les charger si besoin) : {others}."
            )
        return "\n".join(parts)
