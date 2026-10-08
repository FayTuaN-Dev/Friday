"""Le carnet de plans écrits (data/trading_plans.json) : autant de stratégies écrites que tu
veux, chacune avec son nom, son texte, et ses règles une fois traduite (par Claude, après
aperçu). Chaque plan traduit devient une stratégie « ton plan « Nom » » : comparée, choisie,
suivie par les alertes, la check-list et le briefing.

Le plan unique d'avant (data/trading_plan.txt et sa traduction) est repris tel quel comme
premier plan, la première fois."""

import hashlib
import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from friday.trading.strategies.custom import CustomStrategy
from friday.trading.strategies.spec import SpecError, validate
from friday.voice.wake import normalize

log = logging.getLogger(__name__)
PREFIX = "plan:"  # nom de stratégie d'un plan écrit : « plan:<id> »
TEXT_CHARS = 1500  # un plan de trading, pas un roman


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


class PlanBook:
    def __init__(self, path: Path | None, legacy_text: Path | None = None,
                 legacy_rules: Path | None = None) -> None:  # fmt: skip
        self.path, self._lock = path, threading.Lock()
        if path is not None and not path.is_file():
            self._adopt(legacy_text, legacy_rules)

    # --- lecture ----------------------------------------------------------------------------------

    def plans(self) -> list[dict]:
        """[{"id", "nom", "texte", "spec" ou None, "empreinte", "traduit_le"}], dans l'ordre."""
        if self.path is None or not self.path.is_file():
            return []
        try:
            plans = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            log.warning("Carnet de plans illisible (%s)", self.path)
            return []
        for plan in plans:
            try:
                plan["spec"] = validate(plan["spec"]) if plan.get("spec") else None
            except SpecError:
                plan["spec"] = None
        return plans

    def get(self, plan_id: str) -> dict | None:
        return next((p for p in self.plans() if p["id"] == plan_id), None)

    def find(self, text: str) -> dict | None:
        """Le plan dont le nom figure dans la phrase (« teste le plan Cassure Londres »)."""
        padded = f" {normalize(text)} "
        named = [p for p in self.plans() if normalize(p["nom"]) and
                 f" {normalize(p['nom'])} " in padded]  # fmt: skip
        return max(named, key=lambda p: len(p["nom"]), default=None)

    def strategies(self) -> list[CustomStrategy]:
        return [self.strategy(p) for p in self.plans() if p["spec"]]

    def strategy(self, plan: dict) -> CustomStrategy:
        found = CustomStrategy(plan["spec"])
        found.name, found.label = PREFIX + plan["id"], f"ton plan « {plan['nom']} »"
        return found

    def outdated(self, plan: dict) -> bool:
        return bool(plan.get("spec")) and plan.get("empreinte") != fingerprint(plan["texte"])

    # --- écriture ---------------------------------------------------------------------------------

    def add(self, nom: str, texte: str = "") -> dict:
        plans = self.plans()
        plan = {
            "id": self._new_id(plans),
            "nom": self._unique(nom or "Nouveau plan", plans),
            "texte": texte[:TEXT_CHARS],
            "spec": None,
            "empreinte": "",
            "traduit_le": "",
        }
        self._save([*plans, plan])
        return plan

    def update(self, plan_id: str, nom: str | None = None, texte: str | None = None) -> None:
        plans = self.plans()
        for plan in plans:
            if plan["id"] == plan_id:
                if nom is not None and nom.strip():
                    others = [p for p in plans if p["id"] != plan_id]
                    plan["nom"] = self._unique(nom.strip(), others)
                if texte is not None:
                    plan["texte"] = texte.strip()[:TEXT_CHARS]
        self._save(plans)

    def duplicate(self, plan_id: str) -> dict | None:
        source = self.get(plan_id)
        if source is None:
            return None
        copy = self.add(f"{source['nom']} (copie)", source["texte"])
        return copy

    def delete(self, plan_id: str) -> bool:
        plans = self.plans()
        kept = [p for p in plans if p["id"] != plan_id]
        self._save(kept)
        return len(kept) < len(plans)

    def save_translation(self, plan_id: str, spec: dict, texte: str) -> None:
        plans = self.plans()
        for plan in plans:
            if plan["id"] == plan_id:
                plan.update(spec=validate(spec), empreinte=fingerprint(texte),
                            traduit_le=f"{datetime.now():%d/%m/%Y à %H:%M}")  # fmt: skip
        self._save(plans)

    # --- interne ----------------------------------------------------------------------------------

    def _save(self, plans: list[dict]) -> None:
        if self.path is None:
            return
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(plans, indent=2, ensure_ascii=False), "utf-8")

    @staticmethod
    def _new_id(plans: list[dict]) -> str:
        numbers = [int(p["id"][1:]) for p in plans if p["id"][1:].isdigit()]
        return f"p{max(numbers, default=0) + 1}"

    @staticmethod
    def _unique(nom: str, plans: list[dict]) -> str:
        taken, candidate, n = {normalize(p["nom"]) for p in plans}, nom[:60], 2
        while normalize(candidate) in taken:
            candidate, n = f"{nom[:55]} {n}", n + 1
        return candidate

    def _adopt(self, legacy_text: Path | None, legacy_rules: Path | None) -> None:
        """La première fois : le plan unique d'avant devient « Mon plan »."""
        texte = ""
        if legacy_text is not None and legacy_text.is_file():
            texte = legacy_text.read_text("utf-8").strip()
        if not texte:
            return
        plan = self.add("Mon plan", texte)
        try:
            old = json.loads(legacy_rules.read_text("utf-8")) if legacy_rules else None
        except (OSError, ValueError):
            old = None
        if old and old.get("spec"):
            plans = self.plans()
            plans[0].update(spec=old["spec"], empreinte=old.get("empreinte", ""),
                            traduit_le=old.get("traduit_le", ""))  # fmt: skip
            self._save(plans)
        log.info("Plan « %s » repris dans le carnet de plans", plan["nom"])
