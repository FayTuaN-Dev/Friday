"""Réglages du briefing du matin (data/briefing.json) : activé ou non, plage horaire, rubriques.

Pensé pour être modifié aussi bien à la voix (outil configure_briefing) que, plus tard, par
l'écran de réglages : tout passe par load() / save().
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# Types de rubriques : météo, agenda Google du jour, rappels du jour, mails non lus, contenu
# d'une liste, actualité d'un sujet, rubrique libre (une consigne pour Friday : « un conseil
# sport », « une citation »…)
KINDS = ("meteo", "agenda", "rappels", "mails", "liste", "actualites", "libre")
NEEDS_VALUE = {"liste", "actualites", "libre"}
OPTIONAL_VALUE = {"meteo"}  # la ville (sinon HOME_CITY)


@dataclass
class Section:
    kind: str
    value: str = ""

    def label(self) -> str:
        return {
            "meteo": f"Météo du jour ({self.value})" if self.value else "Météo du jour",
            "agenda": "Agenda du jour",
            "rappels": "Rappels du jour",
            "mails": "Mails non lus",
            "liste": f"Liste « {self.value} »",
            "actualites": f"Actualité : {self.value}",
            "libre": self.value.capitalize(),
        }.get(self.kind, self.kind)


def default_sections() -> list[Section]:
    return [Section("meteo"), Section("rappels")]


@dataclass
class BriefingConfig:
    enabled: bool = True
    start_hour: int = 5  # le briefing automatique a lieu entre ces heures
    end_hour: int = 12
    on_greeting: bool = True  # attendre le premier « bonjour » (sinon : dès le démarrage)
    sections: list[Section] = field(default_factory=default_sections)
    last_run: str | None = None  # date (AAAA-MM-JJ) du dernier briefing automatique

    @classmethod
    def load(cls, path: Path) -> "BriefingConfig":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as error:
            log.warning("Réglages du briefing illisibles (%s) : valeurs par défaut", error)
            return cls()
        sections = [Section(**s) for s in data.pop("sections", []) if s.get("kind") in KINDS]
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known, sections=sections)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
