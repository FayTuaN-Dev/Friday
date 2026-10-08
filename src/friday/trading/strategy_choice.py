"""Quelle stratégie suivre (data/trading_strategies.json) : celle choisie pour un instrument,
sinon celle par défaut (Réglages → Trading), sinon ton plan écrit s'il est traduit, sinon le
modèle « repli ». C'est elle que suivent alertes, check-list, briefing et backtest.

Le plan écrit traduit en règles est gardé à part (data/trading_plan_rules.json), avec
l'empreinte du texte traduit : un plan modifié depuis se voit (« à retraduire »)."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from friday.trading.strategies import BY_NAME, STRATEGIES, Strategy
from friday.trading.strategies.custom import CustomStrategy
from friday.trading.strategies.plan import PlanStrategy
from friday.trading.strategies.spec import SpecError, validate

log = logging.getLogger(__name__)
DEFAULT = "_defaut"  # clé du choix par défaut dans le fichier
MINE = "mon_plan"


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


class StrategyChoice:
    def __init__(self, path: Path | None, custom_path: Path | None = None) -> None:
        self.path, self.custom_path = path, custom_path

    # --- le plan écrit, traduit ------------------------------------------------------------------

    def translated(self) -> dict | None:
        """{"spec", "empreinte", "traduit_le"} ou None."""
        if self.custom_path is None or not self.custom_path.is_file():
            return None
        try:
            data = json.loads(self.custom_path.read_text("utf-8"))
            data["spec"] = validate(data["spec"])
            return data
        except (OSError, ValueError, KeyError, TypeError, SpecError):
            log.warning("Règles du plan écrit illisibles (%s)", self.custom_path)
            return None

    def custom(self) -> CustomStrategy | None:
        found = self.translated()
        return CustomStrategy(found["spec"]) if found else None

    def save_translation(self, spec: dict, plan_text: str) -> None:
        self.custom_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"spec": validate(spec), "empreinte": fingerprint(plan_text),
                "traduit_le": f"{datetime.now():%d/%m/%Y à %H:%M}"}  # fmt: skip
        self.custom_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

    def outdated(self, plan_text: str) -> bool:
        """Le plan a-t-il changé depuis sa traduction ?"""
        found = self.translated()
        return found is not None and found.get("empreinte") != fingerprint(plan_text)

    # --- le choix --------------------------------------------------------------------------------

    def available(self) -> tuple[Strategy, ...]:
        mine = self.custom()
        return ((mine,) if mine else ()) + STRATEGIES

    def chosen(self) -> dict[str, str]:
        if self.path is None or not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text("utf-8"))
            return {k: v for k, v in data.items() if v in BY_NAME or v == MINE}
        except (OSError, ValueError, AttributeError):
            log.warning("Choix des stratégies illisible (%s) : choix par défaut", self.path)
            return {}

    def default(self) -> Strategy:
        return self._named(self.chosen().get(DEFAULT, MINE))

    def get(self, symbol: str) -> Strategy:
        name = self.chosen().get(symbol)
        return self._named(name) if name else self.default()

    def set(self, symbol: str, name: str) -> None:
        """`symbol` = DEFAULT : le choix pour tous les instruments sans choix propre."""
        data = self.chosen()
        data[symbol] = name
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), "utf-8")

    def _named(self, name: str) -> Strategy:
        if name == MINE:
            return self.custom() or PlanStrategy()  # pas encore traduit : le modèle
        return BY_NAME.get(name, PlanStrategy())
