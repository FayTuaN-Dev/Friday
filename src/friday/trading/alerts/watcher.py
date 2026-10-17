"""La surveillance des alertes, en arrière-plan, tant que Friday tourne (rien en ligne d'autre
que les cours publics Yahoo ; le graphique TradingView n'est lu que par son titre).

- « niveau » : vérifiée chaque minute, à toute heure ; annoncée une fois puis retirée.
- « setup » : vérifiée à chaque nouvelle bougie 1 h fermée, PENDANT les heures de trading
  (Réglages → Trading) ; annoncée quand le setup APPARAÎT, pas tant qu'il dure.

Le cours d'un instrument : celui du graphique TradingView s'il l'affiche (le plus juste) ;
sinon Yahoo, recalé du dernier écart vu avec le graphique (contrat à terme contre comptant).
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from friday.trading.alerts import setup as setups
from friday.trading.alerts.store import Alert, AlertStore
from friday.trading.instruments import Instrument, by_symbol, chart_price
from friday.trading.market import MarketUnavailable, _digits, fetch
from friday.trading.plan_rules import load_rules
from friday.trading.sessions import PARIS

log = logging.getLogger(__name__)
SETUP_EVERY = 300  # secondes entre deux lectures des bougies d'un même instrument


def yahoo_price(instrument: Instrument) -> float:
    return fetch(instrument.yahoo, "1d", "5d")[0].price


def yahoo_history(instrument: Instrument):
    """(bougies 1 h sur 6 mois : de quoi calculer une période de 1 500 bougies, cf. spec.py ;
    journalières sur 2 ans pour l'EMA200)."""
    return fetch(instrument.yahoo, "1h", "6mo")[1], fetch(instrument.yahoo, "1d", "2y")[1]


class AlertWatcher:
    def __init__(
        self, store: AlertStore, rules_path: Path | None = None,
        chart_title: Callable[[], str | None] = lambda: None, quote=yahoo_price,
        history=yahoo_history, now: Callable[[], datetime] = lambda: datetime.now(UTC),
        hours: tuple[int, int] = (9, 18), interval: float = 60,
    ) -> None:  # fmt: skip
        self.store, self.rules_path, self.chart_title = store, rules_path, chart_title
        self.quote, self.history, self.now = quote, history, now
        self.hours, self.interval = hours, interval
        self.on_alert: Callable[[str], None] = lambda text: None  # branché au démarrage
        self.choice = None  # StrategyChoice : la stratégie de chaque instrument (le plan sinon)
        self._announced: dict[str, datetime] = {}  # symbole → dernière bougie examinée
        self._read: dict[str, datetime] = {}  # symbole → dernière lecture des bougies
        self._said: dict[str, tuple] = {}  # symbole → dernier setup annoncé (sens, bougie)
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="trading-alerts").start()

    def stop(self) -> None:
        self._stop.set()

    def price(self, instrument: Instrument) -> tuple[float, bool]:
        """(cours sur l'échelle du graphique de l'utilisateur, vu sur le graphique ?)"""
        title = self.chart_title()
        shown = chart_price(title, instrument) if title else None
        if shown is not None:
            if instrument.note:  # contrat à terme : on retient l'écart pour plus tard
                self.store.set_offset(instrument.symbol, self.quote(instrument) - shown)
            return shown, True
        return self.quote(instrument) - self.store.offsets.get(instrument.symbol, 0.0), False

    def check(self) -> None:
        for alert in self.store.all():
            instrument = by_symbol(alert.symbol)
            if instrument is None:
                continue
            try:
                if alert.kind == "niveau":
                    self._check_level(alert, instrument)
                elif self._trading_hours():
                    self._check_setup(instrument)
            except MarketUnavailable as error:
                log.info("Alerte n°%d non vérifiée : %s", alert.id, error)

    def _check_level(self, alert: Alert, instrument: Instrument) -> None:
        price, _ = self.price(instrument)
        if (price >= alert.level) if alert.above else (price <= alert.level):
            if self.store.remove(alert.id):
                way = "au-dessus de" if alert.above else "sous"
                digits = _digits(instrument)
                fr = lambda x: f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")  # noqa: E731
                self.on_alert(f"Alerte : {instrument.name} est passé {way} "
                              f"{fr(alert.level)} (cours {fr(price)}).")  # fmt: skip

    def _check_setup(self, instrument: Instrument) -> None:
        now, last = self.now(), self._read.get(instrument.symbol)
        if last is not None and (now - last).total_seconds() < SETUP_EVERY:
            return  # Yahoo ménagé : une lecture toutes les 5 min au plus
        self._read[instrument.symbol] = now
        hourly, daily = self.history(instrument)
        hourly = setups.closed(hourly, now)
        if not hourly or self._announced.get(instrument.symbol) == hourly[-1].time:
            return
        rules = load_rules(self.rules_path)
        strategy = self.choice.get(instrument.symbol) if self.choice is not None else None
        self._announced[instrument.symbol] = hourly[-1].time
        if strategy is not None and not strategy.covers(instrument):
            return  # la stratégie ne suit pas cette famille de marchés (Réglages)
        found = setups.detect(hourly, daily, rules, strategy)
        if found is None:
            return
        key = (found.side, found.bar.time)  # une journée : vue à chaque heure, annoncée une fois
        if self._said.get(instrument.symbol) == key:
            return
        self._said[instrument.symbol] = key
        if setups.lasting(hourly, daily, rules, strategy, found):
            return  # le setup dure depuis la bougie d'avant : déjà annoncé (ou en cours)
        shift = self.store.offsets.get(instrument.symbol, 0.0)
        self.on_alert(setups.announcement(instrument, found, rules, shift))

    def _trading_hours(self) -> bool:
        local = self.now().astimezone(PARIS)
        return local.weekday() < 5 and self.hours[0] <= local.hour < self.hours[1]

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.check()
            except Exception:
                log.exception("Erreur dans la surveillance des alertes")
