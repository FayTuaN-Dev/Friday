"""Quand rêver (J2) : chaque journée passée qui a des échanges est relue une fois, la nuit
(2 h – 6 h) ou dès que Friday est inactive depuis 30 min (PC éteint la nuit). Le rapport est
gardé dans data/reve/ ; une notification SILENCIEUSE le signale (Friday ne parle pas à 3 h)
et « qu'as-tu fait cette nuit ? » le lit (tools/dream_report.py)."""

import json
import logging
import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from friday.memory.day_log import DayLog, day_name
from friday.memory.dream import Dreamer, Report, repeated_errors, stale
from friday.memory.service import MemoryService
from friday.tools.base import ToolResult

log = logging.getLogger(__name__)

TASK = "rêve de la nuit"  # tâche de fond silencieuse (app/notification.py)
NIGHT = range(2, 6)
IDLE = timedelta(minutes=30)
LOOK_BACK = 3  # jours relus au plus (PC éteint plusieurs jours)
CHECK_EVERY = 600  # secondes


class NightDream:
    def __init__(self, memory: MemoryService, day_log: DayLog, dreamer: Dreamer, folder: Path,
                 log_file: Path, on_done: Callable[[str, ToolResult], None] | None = None,
                 ) -> None:  # fmt: skip
        self.memory, self.day_log, self.dreamer = memory, day_log, dreamer
        self.folder, self.log_file, self.on_done = folder, log_file, on_done
        self._stop = threading.Event()

    # --- Quand ---

    def done_days(self) -> set[str]:
        try:
            return set(json.loads((self.folder / "etat.json").read_text("utf-8"))["done"])
        except (OSError, ValueError, KeyError, TypeError):
            return set()

    def due_days(self, now: datetime) -> list[date]:
        done, today = self.done_days(), now.date()
        days = [today - timedelta(days=n) for n in range(LOOK_BACK, 0, -1)]
        return [d for d in days if d.isoformat() not in done and self.day_log.day(d)]

    def can_run(self, now: datetime) -> bool:
        last = self.day_log.last_time()
        return now.hour in NIGHT or last is None or now - last >= IDLE

    def tick(self, now: datetime | None = None) -> list[Report]:
        now = now or datetime.now()
        if not self.can_run(now):
            return []
        return [self.dream(day, now) for day in self.due_days(now)]

    def start(self) -> None:
        def loop() -> None:
            while not self._stop.wait(CHECK_EVERY):
                try:
                    self.tick()
                except Exception:
                    log.exception("Rêve nocturne impossible")

        threading.Thread(target=loop, daemon=True, name="night-dream").start()

    # --- Rêver ---

    def dream(self, day: date, now: datetime) -> Report:
        exchanges = self.day_log.day(day)
        report = Report(day.isoformat(), len(exchanges))
        name = day_name(day, now.date())
        for fact, said in self.dreamer.missed_facts(exchanges, self.memory.all(), name):
            before = len(self.memory.all())
            memory = self.memory.remember(fact.text, "auto", fact.replaces, fact.category,
                                          said=said)  # fmt: skip
            if len(self.memory.all()) > before or fact.replaces:
                report.added.append(memory.text)
        active = self.memory.all()
        report.pairs = self.dreamer.pairs(active)
        report.stale = stale(active, now)
        report.errors = repeated_errors(self.log_file)
        said = report.added + [m.text for p in report.pairs for m in (p.first, p.second)]
        report.you = self.dreamer.to_you(said + [m.text for m in report.stale])
        self._save(report)
        log.info("Rêve du %s : %d échanges, %d faits retenus, %d points à vérifier", report.day,
                 report.exchanges, len(report.added), report.to_check)  # fmt: skip
        if self.on_done is not None:
            self.on_done(TASK, ToolResult(f"Dis EXACTEMENT : « {headline(report)} »"))
        return report

    def _save(self, report: Report) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{report.day}.md").write_text(markdown(report), "utf-8")
        data = json.dumps(as_data(report), ensure_ascii=False)
        (self.folder / "dernier.json").write_text(data, "utf-8")
        done = sorted(self.done_days() | {report.day})[-60:]
        (self.folder / "etat.json").write_text(json.dumps({"done": done}), "utf-8")


def headline(report: Report) -> str:
    plural = "s" if report.exchanges > 1 else ""
    parts = [f"J'ai relu nos {report.exchanges} échange{plural}"]
    if report.added:
        parts.append(f"retenu {len(report.added)} chose{'s' if len(report.added) > 1 else ''}")
    if report.to_check:
        parts.append(f"{report.to_check} point{'s' if report.to_check > 1 else ''} à vérifier")
    return ", ".join(parts) + ". Demande-moi « qu'as-tu fait cette nuit ? »."


def as_data(report: Report) -> dict:
    return {"day": report.day, "exchanges": report.exchanges, "added": report.added,
            "pairs": [{"kind": p.kind, "a": [p.first.id, p.first.text],
                       "b": [p.second.id, p.second.text]} for p in report.pairs],
            "stale": [[m.id, m.text] for m in report.stale],
            "errors": [[text, n] for text, n in report.errors], "you": report.you}  # fmt: skip


def markdown(report: Report) -> str:
    lines = [f"# Rêve du {report.day}", "", f"{report.exchanges} échanges relus.", ""]
    lines += ["## Retenu", *(f"- {text}" for text in report.added or ["rien de nouveau"]), ""]
    lines.append("## À vérifier (rien n'a été changé)")
    for pair in report.pairs:
        lines.append(f"- {pair.kind} : [{pair.first.id}] {pair.first.text} / "
                     f"[{pair.second.id}] {pair.second.text}")  # fmt: skip
    lines += [f"- jamais redit depuis 6 mois : [{m.id}] {m.text}" for m in report.stale]
    lines += [f"- erreur répétée ({n} fois) : {text}" for text, n in report.errors]
    if not report.to_check:
        lines.append("- rien")
    return "\n".join(lines) + "\n"
