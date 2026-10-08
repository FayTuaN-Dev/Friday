"""Alertes de trading (T3) : niveaux et setup du plan surveillés en local, annoncés à la voix."""

from datetime import UTC, datetime, timedelta

from test_backtest import DAILY, bars, setup_closes

from friday.tools.alerts import CancelAlertTool, ListAlertsTool, PriceAlertTool, WatchSetupTool
from friday.trading.alerts.setup import closed, detect
from friday.trading.alerts.store import AlertStore
from friday.trading.alerts.watcher import AlertWatcher
from friday.trading.instruments import by_symbol
from friday.trading.market import MarketUnavailable
from friday.trading.mode import TradingMode
from friday.trading.plan_rules import PlanRules

GOLD = by_symbol("XAUUSD")
START = datetime(2026, 9, 4, 3, tzinfo=UTC)  # la bougie du setup (n°127) : mercredi 10 h UTC
SETUP_BAR = START + timedelta(hours=127)


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def __call__(self):
        return self.moment


def make_watcher(tmp_path, quote=4130.0, title=None, hourly=None, clock=None):
    said = []
    hourly = hourly or bars(setup_closes()[:128] + [4290], START)  # + la bougie en cours
    watcher = AlertWatcher(
        AlertStore(tmp_path / "alerts.json"), tmp_path / "rules.json",
        chart_title=lambda: title, quote=lambda i: quote if not callable(quote) else quote(i),
        history=lambda i: (hourly, DAILY), now=clock or Clock(SETUP_BAR + timedelta(minutes=65)),
    )  # fmt: skip
    watcher.on_alert = said.append
    return watcher, said


def test_store_keeps_alerts_and_offsets_across_restarts(tmp_path):
    path = tmp_path / "alerts.json"
    store = AlertStore(path)
    level = store.add_level("XAUUSD", 4150, above=True)
    watch = store.add_setup("EURUSD")
    assert store.add_setup("EURUSD").id == watch.id  # pas de doublon
    store.set_offset("XAUUSD", 25.4)
    again = AlertStore(path)
    assert [(a.id, a.kind) for a in again.all()] == [(1, "niveau"), (2, "setup")]
    assert again.offsets == {"XAUUSD": 25.4} and again.all()[0].level == 4150
    assert again.remove(level.id) and not again.remove(99) and again.clear() == 1
    path.write_text("{abîmé", "utf-8")
    assert AlertStore(path).all() == []


def test_price_comes_from_the_chart_and_remembers_the_futures_gap(tmp_path):
    watcher, _ = make_watcher(tmp_path, quote=4155.0, title="XAUUSD 4 130,0 ▲ +0.4%")
    assert watcher.price(GOLD) == (4130.0, True)
    assert watcher.store.offsets["XAUUSD"] == 25.0
    watcher.chart_title = lambda: None
    assert watcher.price(GOLD) == (4130.0, False)  # Yahoo recalé sur l'écart retenu
    eur, _ = make_watcher(tmp_path, quote=1.16, title="EURUSD 1,16000")
    eur.price(by_symbol("EURUSD"))
    assert "EURUSD" not in eur.store.offsets  # pas un contrat à terme


def test_level_alert_fires_once_in_its_direction(tmp_path):
    watcher, said = make_watcher(tmp_path, quote=4140.0)
    up = watcher.store.add_level("XAUUSD", 4150, above=True)
    down = watcher.store.add_level("XAUUSD", 4100, above=False)
    watcher.check()
    assert said == []
    watcher.quote = lambda i: 4152.3
    watcher.check()
    watcher.check()
    assert said == ["Alerte : l'or est passé au-dessus de 4 150,00 (cours 4 152,30)."]
    assert [a.id for a in watcher.store.all()] == [down.id] and up.id != down.id


def test_a_market_outage_does_not_stop_the_watch(tmp_path):
    def broken(instrument):
        raise MarketUnavailable("Yahoo en panne.")

    watcher, said = make_watcher(tmp_path, quote=broken)
    watcher.store.add_level("XAUUSD", 4150, above=True)
    watcher.check()
    assert said == [] and len(watcher.store.all()) == 1


def test_setup_is_announced_when_it_appears_with_indicative_levels(tmp_path):
    hourly = bars(setup_closes()[:128], START)
    assert detect(hourly, DAILY, PlanRules()) is not None
    assert detect(hourly[:-1], DAILY, PlanRules()) is None  # il apparaît sur cette bougie
    watcher, said = make_watcher(tmp_path)
    watcher.store.add_setup("XAUUSD")
    watcher.check()
    (text,) = said
    assert text.startswith("Alerte setup « le repli sur moyenne (modèle) » sur l'or : achat dans "
                           "le sens de l'EMA200 journalière")  # fmt: skip
    assert "bougie 1 h fermée à 13:00 à 4 284,00" in text and "RSI 48 qui remonte" in text
    assert "stop indicatif 4 269,00, objectif 2 R 4 314,00" in text
    watcher._read.clear()
    watcher.check()
    assert len(said) == 1  # même bougie : pas de répétition


def test_setup_levels_follow_the_chart_gap_and_trading_hours(tmp_path):
    watcher, said = make_watcher(tmp_path)
    watcher.store.add_setup("XAUUSD")
    watcher.store.set_offset("XAUUSD", 25.0)
    watcher.check()
    assert "stop indicatif 4 244,00" in said[0]  # 4 269 − 25
    night, quiet = make_watcher(tmp_path / "n", clock=Clock(SETUP_BAR + timedelta(hours=12)))
    night.store.add_setup("XAUUSD")
    night.check()
    assert quiet == []  # 22 h à Paris : hors des heures de trading


def test_the_candle_in_progress_is_ignored():
    hourly = bars([1, 2, 3], START)
    assert closed(hourly, START + timedelta(hours=2, minutes=30)) == hourly[:2]
    assert closed(hourly, START + timedelta(hours=3)) == hourly


def test_alert_tools(tmp_path):
    watcher, _ = make_watcher(tmp_path, quote=4155.0)
    text = PriceAlertTool(watcher).run("or", 4100).text
    assert "alerte n°1 : l'or sous 4 100,00 ; le cours est à 4 155,00" in text
    assert "ouvre le graphique pour l'aligner" in text  # contrat à terme sans graphique
    assert "Je surveille l'or" in WatchSetupTool(watcher).run("l'or").text
    listing = ListAlertsTool(watcher).run()
    assert [i["text"] for i in listing.display.data["items"]] == [
        "n°1 : l'or sous 4 100,00",
        "n°2 : setup du plan sur l'or (bougies 1 h, heures de trading)",
    ]
    cancel = CancelAlertTool(watcher)
    assert "Alerte n°1 annulée" in cancel.run(1).text and "Pas d'alerte n°1" in cancel.run(1).text
    assert "1 alerte(s) annulée(s)" in cancel.run(all=True).text
    assert "Aucune alerte" in ListAlertsTool(watcher).run().text
    assert "Alerte impossible" in PriceAlertTool(watcher).run("zzzz-??", 1).text


def test_alerts_are_announced_with_a_chime(tmp_path):
    from friday.app.trading_alerts import start_alerts

    class Voice:
        chimes = 0

        def chime(self):
            Voice.chimes += 1

    watcher, _ = make_watcher(tmp_path)
    watcher.interval = 3600  # pas de vérification pendant le test
    done = []
    start_alerts(watcher, lambda: Voice(), lambda task, result: done.append((task, result)))
    watcher.on_alert("Alerte : l'or est passé au-dessus de 4 150,00 (cours 4 152,30).")
    watcher.stop()
    assert Voice.chimes == 1 and done[0][0] == "alerte"
    assert "Dis EXACTEMENT : « Alerte : l'or est passé" in done[0][1].text


def test_alert_requests_and_announcements_stay_local():
    mode = TradingMode()
    for text in ("préviens-moi si l'or passe 4150", "surveille l'or", "mes alertes",
                 "annule l'alerte 2", "(Message automatique) ALERTE DE TRADING"):  # fmt: skip
        assert mode.route(text) == "local", text
