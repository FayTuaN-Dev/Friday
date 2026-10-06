"""Le contexte joint à une analyse, en plus des données de marché : annonces économiques,
actualités, positionnement COT, séances, et le plan de trading de l'utilisateur.

Chaque source est indépendante : si l'une ne répond pas, les autres partent quand même et
l'aperçu dit ce qui manque. Tout ce qui est public (annonces, actualités, COT, séances) ne dit
rien de l'utilisateur ; son plan, lui, est masqué comme sa question.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from friday.trading import calendar, cot, news, sessions
from friday.trading.cache import age_note
from friday.trading.calendar import SourceUnavailable
from friday.trading.instruments import Instrument

PLAN_CHARS = 1500  # un plan de trading, pas un roman


def load_plan(path: Path) -> str:
    try:
        return path.read_text("utf-8").strip()
    except OSError:
        return ""


def save_plan(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", "utf-8")


@dataclass
class Block:
    kind: str  # « calendrier », « actualites », « positionnement », « seances », « plan »
    source: str
    text: str


class ContextSources:
    def __init__(
        self, plan_path: Path | None = None, cache_dir: Path | None = None, events=None,
        headlines=news.fetch_headlines, cot_rows=None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:  # fmt: skip
        """`events`, `cot_rows` : () → données, ou (données, âge d'une vieille copie)."""
        self.plan_path = plan_path
        cache = (lambda name: cache_dir / name) if cache_dir else (lambda name: None)
        self.events = events or (lambda: calendar.load(cache("ff_calendar.json")))
        self.cot_rows = cot_rows or (lambda: cot.load(cache("cot.txt")))
        self.headlines, self.now = headlines, now
        self._notes: list[str] = []

    def blocks(self, instrument: Instrument) -> tuple[list[Block], list[str]]:
        """(blocs à joindre, notes pour l'aperçu)."""
        now, found, notes = self.now(), [], []
        self._notes = notes
        steps = (
            ("calendrier", "calendrier économique (ForexFactory)",
             lambda: calendar.text(calendar.relevant(
                 self._data(self.events, "Calendrier économique"), instrument.currencies, now),
                 now)),
            ("actualites", "actualités (FXStreet)",
             lambda: news.text(news.relevant(self.headlines(), instrument, now))),
            ("positionnement", "positionnement COT (CFTC)", lambda: self._cot(instrument)),
        )  # fmt: skip
        for kind, source, make in steps:
            try:
                found.append(Block(kind, source, make()))
            except SourceUnavailable as error:
                notes.append(f"{error} Analyse sans ce bloc.")
        found.append(Block("seances", "heure et séances (calcul sur le PC)", sessions.text(now)))
        plan = load_plan(self.plan_path) if self.plan_path else ""
        if plan:
            found.append(Block("plan", "votre plan de trading", plan[:PLAN_CHARS]))
        return found, notes

    def _data(self, fetch, source: str):
        """Les données, en notant pour l'aperçu si c'est une vieille copie."""
        result = fetch()
        if isinstance(result, tuple):
            result, age = result
            if note := age_note(source, age):
                self._notes.append(note)
        return result

    def _cot(self, instrument: Instrument) -> str:
        rows = self._data(self.cot_rows, "Rapport COT")
        found = [p for p in (cot.positioning(rows, m) for m in cot.markets_for(instrument)) if p]
        return cot.text(found)
