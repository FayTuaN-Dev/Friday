"""Les alertes, gardées sur le PC (data/trading_alerts.json) : elles survivent à un
redémarrage. « niveau » : une seule fois, puis supprimée ; « setup » : jusqu'à son retrait.

On y garde aussi, par instrument, le dernier écart vu entre Yahoo et le graphique TradingView
(contrat à terme contre comptant : ~25 points sur l'or) pour recaler les niveaux quand le
graphique n'est pas affiché."""

import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class Alert:
    id: int
    kind: str  # « niveau » ou « setup »
    symbol: str  # XAUUSD, EURUSD…
    level: float | None = None
    above: bool | None = None  # se déclenche au-dessus (True) ou en dessous (False) du niveau
    created: str = ""


class AlertStore:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._alerts: list[Alert] = []
        self.offsets: dict[str, float] = {}  # écart Yahoo − graphique, par symbole
        self._load()

    def all(self) -> list[Alert]:
        with self._lock:
            return list(self._alerts)

    def add_level(self, symbol: str, level: float, above: bool) -> Alert:
        return self._add(Alert(0, "niveau", symbol, level, above))

    def add_setup(self, symbol: str) -> Alert:
        """Une seule surveillance par instrument : la redemander rend l'existante."""
        found = next((a for a in self.all() if a.kind == "setup" and a.symbol == symbol), None)
        return found or self._add(Alert(0, "setup", symbol))

    def remove(self, alert_id: int) -> bool:
        with self._lock:
            before = len(self._alerts)
            self._alerts = [a for a in self._alerts if a.id != alert_id]
            removed = len(self._alerts) < before
        if removed:
            self._save()
        return removed

    def remove_setups(self) -> int:
        """Fin de la surveillance des marchés : les alertes de prix restent."""
        with self._lock:
            kept = [a for a in self._alerts if a.kind != "setup"]
            count, self._alerts = len(self._alerts) - len(kept), kept
        self._save()
        return count

    def clear(self) -> int:
        with self._lock:
            count, self._alerts = len(self._alerts), []
        self._save()
        return count

    def set_offset(self, symbol: str, offset: float) -> None:
        if abs(self.offsets.get(symbol, 0.0) - offset) > 1e-9:
            self.offsets[symbol] = offset
            self._save()

    def _add(self, alert: Alert) -> Alert:
        with self._lock:
            alert.id = max((a.id for a in self._alerts), default=0) + 1
            alert.created = f"{datetime.now():%Y-%m-%d %H:%M}"
            self._alerts.append(alert)
        self._save()
        return alert

    def _load(self) -> None:
        if self.path is None or not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text("utf-8"))
            self._alerts = [Alert(**a) for a in data.get("alerts", [])]
            self.offsets = {k: float(v) for k, v in data.get("offsets", {}).items()}
        except (OSError, ValueError, TypeError):
            log.warning("Alertes illisibles (%s) : on repart de zéro", self.path)

    def _save(self) -> None:
        if self.path is None:
            return
        with self._lock:
            data = {"alerts": [asdict(a) for a in self._alerts], "offsets": self.offsets}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
