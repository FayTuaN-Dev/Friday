"""Les outils et consignes donnés au modèle pour UNE demande : le noyau, les compétences
choisies par l'aiguillage, celles de l'échange précédent, et celles que le modèle charge
lui-même (load_skill) s'il lui en manque une."""

import logging
from collections.abc import Callable
from typing import Any

from friday.brain.router import SkillRouter
from friday.brain.skills import BY_NAME, CORE_GUIDE, CORE_TOOLS, SKILLS
from friday.tools.base import ToolBox

LOAD_SKILL = "load_skill"
# Une compétence qui a servi reste active tant que la conversation continue sans changer de
# sujet (« approfondis », « et le troisième ? », « garde ça »), au plus ce nombre d'échanges.
STICKY_TURNS = 3
log = logging.getLogger(__name__)


class Toolset:
    def __init__(
        self,
        toolbox: ToolBox,
        router: SkillRouter | None = None,
        contexts: dict[str, Callable[[], str]] | None = None,
        hints: dict[str, Callable[[str], str]] | None = None,
        gates: dict[str, Callable[[], bool]] | None = None,
    ) -> None:
        """`contexts` : par compétence, un état réel à donner au modèle quand elle est active
        (ex. les rubriques du briefing), pour qu'il ne l'invente pas.
        `hints` : par compétence, hint(demande) → consigne si elle s'impose pour CETTE
        demande (ex. la bibliothèque parle du sujet), "" sinon ; la compétence est activée.
        `gates` : par compétence, gate() → False la rend inexistante pour l'instant (ex. le
        trading hors du mode trading : ni proposée, ni chargeable)."""
        self.gates = gates or {}
        self.toolbox = toolbox
        self.contexts = contexts or {}
        self.hints = hints or {}
        self._hint_texts: dict[str, str] = {}
        available = set(toolbox.names())
        self._skills = [s for s in SKILLS if available & set(s.tools)]
        skill_tools = {t for s in SKILLS for t in s.tools}
        self._always = (set(CORE_TOOLS) | (available - skill_tools)) & available
        self.router = router
        self.active: set[str] = {s.name for s in self._skills}  # sans aiguillage : tout
        self._fresh: set[str] = set()
        self._previous: dict[str, int] = {}  # compétence → échanges restants

    @property
    def skills(self) -> list:
        """Les compétences utilisables en ce moment (portes ouvertes)."""
        return [s for s in self._skills if self.gates.get(s.name, lambda: True)()]

    def start(self, user_text: str) -> None:
        """Début d'une demande : choisit les compétences actives."""
        if self.router is None:
            return
        available = {s.name for s in self.skills}
        self._fresh = self.router.choose(user_text) & available
        self._hint_texts = {}
        for name, hint in self.hints.items():
            text = hint(user_text) if name in available else ""
            if text:
                self._hint_texts[name] = text
                self._fresh.add(name)
                log.info("Compétence « %s » suggérée : %s", name, text[:80])
        self.active = self._fresh | set(self._previous)

    def load(self, name: str) -> str:
        if name not in BY_NAME or BY_NAME[name] not in self.skills:
            return f"Compétence inconnue : « {name} »."
        self.active.add(name)
        self._fresh.add(name)
        return f"Compétence « {name} » chargée : ses outils sont maintenant disponibles."

    def widen(self) -> bool:
        """Filet de sécurité : donne toutes les compétences pour cette demande. Renvoie False
        s'il n'y avait rien à ajouter."""
        missing = {s.name for s in self.skills} - self.active
        if self.router is None or not missing:
            return False
        self.active |= missing
        return True

    def finish(self) -> None:
        """Fin d'une demande. Nouveau sujet : ses compétences restent pour la suite, les
        anciennes partent. Pas de nouveau sujet : les compétences en cours restent, au plus
        STICKY_TURNS échanges."""
        if self.router is None:
            return
        if self._fresh:
            self._previous = dict.fromkeys(self._fresh, STICKY_TURNS)
        else:
            self._previous = {name: n - 1 for name, n in self._previous.items() if n > 1}

    def _context(self, name: str) -> list[str]:
        if name not in self.contexts:
            return []
        try:
            text = self.contexts[name]()
            return [f"  {text}"] if text else []
        except Exception as error:  # un état illisible ne doit pas bloquer la réponse
            log.warning("Contexte « %s » indisponible : %s", name, error)
            return []

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
        parts = [CORE_GUIDE]
        for skill in self.skills:
            if skill.name in self.active:
                parts.append(skill.guide)
                parts += self._context(skill.name)
                if skill.name in self._hint_texts:
                    parts.append(f"  {self._hint_texts[skill.name]}")
        inactive = [s for s in self.skills if s.name not in self.active]
        if self.router is not None and inactive:
            others = ", ".join(s.label for s in inactive)
            parts.append(
                f"- Tu sais aussi faire (outil load_skill pour les charger si besoin) : {others}."
            )
        return "\n".join(parts)
