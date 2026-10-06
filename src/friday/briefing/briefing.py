"""Le briefing du matin : quand le faire, quoi dire, et la gestion des rubriques."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from friday.briefing.config import KINDS, NEEDS_VALUE, OPTIONAL_VALUE, BriefingConfig, Section
from friday.briefing.sections import Sources, gather
from friday.voice.wake import normalize

REQUEST = """(Message automatique, pas de l'utilisateur.) C'est le briefing du matin. \
Informations du jour, rubrique par rubrique :

{facts}

Commence par un bonjour, puis présente ces informations en quelques phrases naturelles, \
dans cet ordre, sans liste ni Markdown. N'invente rien, n'ajoute rien d'autre (aucun conseil \
ni rappel de ton cru) et ne parle pas des rubriques absentes."""


class Briefing:
    def __init__(self, path: Path, sources: Sources, default_city: str = "") -> None:
        self.path = path
        self.sources = sources
        self.default_city = default_city  # HOME_CITY
        self._lock = threading.Lock()

    @property
    def config(self) -> BriefingConfig:
        return BriefingConfig.load(self.path)  # relu à chaque fois : modifiable de l'extérieur

    def sources_city_known(self) -> bool:
        return bool(self.default_city)

    def summary(self) -> str:
        """Une ligne pour le modèle : les rubriques réelles (il en inventait sinon)."""
        config = self.config
        state = "activé" if config.enabled else "désactivé"
        names = ", ".join(s.label() for s in config.sections) or "aucune rubrique"
        return f"Rubriques actuelles du briefing ({state}) : {names}. N'en cite aucune autre."

    def due(self, now: datetime) -> bool:
        """Briefing automatique : activé, dans la plage horaire, pas encore fait aujourd'hui."""
        c = self.config
        return (
            c.enabled
            and c.start_hour <= now.hour < c.end_hour
            and c.last_run != now.date().isoformat()
        )

    def facts(self, now: datetime) -> str | None:
        """Les rubriques qui ont quelque chose à dire ; None si aucune."""
        sections = self.config.sections
        if not sections:
            return None
        # En parallèle : météo et actualités sont en ligne (l'une après l'autre : ~20 s)
        with ThreadPoolExecutor(max_workers=len(sections)) as pool:
            contents = list(pool.map(lambda s: gather(s, self.sources, now), sections))
        parts = [f"## {s.label()}\n{c}" for s, c in zip(sections, contents, strict=True) if c]
        return "\n\n".join(parts) or None

    def request(self, now: datetime) -> str | None:
        """Demande à faire au cerveau pour le briefing, ou None s'il n'y a rien à dire."""
        facts = self.facts(now)
        return REQUEST.format(facts=facts) if facts else None

    def mark_done(self, now: datetime) -> None:
        self._update(lambda c: setattr(c, "last_run", now.date().isoformat()))

    # --- Rubriques et activation (voix aujourd'hui, écran de réglages plus tard) ---

    def set_hours(self, start: int, end: int) -> None:
        """Plage du briefing automatique (heure de début incluse, de fin exclue)."""
        start, end = max(0, min(start, 23)), max(1, min(end, 24))
        end = max(end, start + 1)
        self._update(lambda c: (setattr(c, "start_hour", start), setattr(c, "end_hour", end)))

    def set_enabled(self, enabled: bool) -> None:
        self._update(lambda c: setattr(c, "enabled", enabled))

    def add(self, kind: str, value: str = "") -> str:
        kind, value = normalize(kind).replace(" ", ""), value.strip()
        if kind not in KINDS:
            return f"Type de rubrique inconnu : {kind}."
        if kind in NEEDS_VALUE and not value:
            return "Il manque le sujet, la liste ou la consigne de cette rubrique."
        section = Section(kind, value if kind in NEEDS_VALUE | OPTIONAL_VALUE else "")
        index = self._find(Section(kind, "" if kind in OPTIONAL_VALUE else section.value))
        if index is not None and kind in OPTIONAL_VALUE:  # « la météo de Lyon » : change la ville
            self._update(lambda c: c.sections.__setitem__(index, section))
            return f"Rubrique mise à jour : {section.label()}."
        if index is not None:
            return f"La rubrique « {section.label()} » y est déjà."
        self._update(lambda c: c.sections.append(section))
        return f"Rubrique ajoutée : {section.label()}."

    def remove(self, kind: str, value: str = "") -> str:
        index = self._find(Section(normalize(kind).replace(" ", ""), value.strip()))
        if index is None:
            return "Je ne trouve pas cette rubrique dans le briefing."
        label = self.config.sections[index].label()
        self._update(lambda c: c.sections.pop(index))
        return f"Rubrique retirée : {label}."

    def _find(self, wanted: Section) -> int | None:
        for i, section in enumerate(self.config.sections):
            same_value = normalize(section.value) == normalize(wanted.value)
            if section.kind == wanted.kind and (same_value or not wanted.value):
                return i
        return None

    def _update(self, change) -> None:
        with self._lock:
            config = self.config
            change(config)
            config.save(self.path)
