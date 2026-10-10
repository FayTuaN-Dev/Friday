"""Briefing trading (T5) : annonces fortes du jour, nuit, niveaux clés, tendance, règles du
plan ; automatique au début de la plage de trading, en semaine, une fois par jour."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from friday.tools.trading_briefing import TradingBriefingTool
from friday.trading.alerts.store import AlertStore
from friday.trading.briefing import _yesterday_close, build
from friday.trading.briefing_service import BriefingService
from friday.trading.calendar import Event
from friday.trading.calendar_fr import french
from friday.trading.instruments import by_symbol
from friday.trading.journal import TradeJournal
from friday.trading.market import Candle, MarketUnavailable
from friday.trading.mode import TradingMode
from friday.trading.plan_rules import PlanRules

EUR = by_symbol("EURUSD")
GOLD = by_symbol("XAUUSD")
NOW = datetime(2026, 10, 7, 7, 30, tzinfo=UTC)  # mercredi 9 h 30 à Paris


def candles(closes, start, hours):
    return [Candle(start + timedelta(hours=i * hours), c, c + 0.002, c - 0.002, c)
            for i, c in enumerate(closes)]  # fmt: skip


def history(instrument):
    """Journalier en hausse (sous le cours : tendance haussière) ; 1 h, de lundi 0 h à
    mercredi 9 h (Paris) : 1,1000 jusqu'à hier 18 h, puis la nuit monte jusqu'à 1,1080."""
    daily = candles([1.0 + 0.0003 * i for i in range(300)], NOW - timedelta(days=301), 24)
    start = datetime(2026, 10, 6, 0, tzinfo=UTC)
    closes = [1.1000] * 16 + [1.1000 + 0.0005 * k for k in range(1, 17)]  # 16 h UTC = 18 h
    return candles(closes, start, 1), daily


def event(hours, title, currency="USD", impact="High"):
    return Event(NOW + timedelta(hours=hours), currency, title, impact, "", "")


def test_announcements_are_translated():
    assert french("Core CPI m/m") == "inflation sous-jacente (CPI hors énergie et alimentation) " \
                                     "sur un mois"  # fmt: skip
    assert french("Unemployment Claims") == "inscriptions hebdomadaires au chômage"
    assert french("Fed Chair Powell Speaks") == "discours du président de la Fed (Powell)"
    assert french("Some New Thing") == "Some New Thing"  # inconnu : l'original


def test_briefing_content_is_computed_by_the_code():
    events = [event(5, "Unemployment Claims"), event(1, "Retail Sales", impact="Medium"),
              event(2, "BOJ Policy Rate", "JPY"), event(30, "CPI m/m"),
              event(-1, "German Prelim CPI m/m", "EUR")]  # fmt: skip
    text = build([EUR], history, events, PlanRules(), NOW, open_trades=1, alerts=2).text()
    assert text.startswith("Briefing trading du mercredi 07/10.")
    assert ("Annonces fortes du jour : 08 h 30, EUR, inflation allemande (estimation) sur un "
            "mois (déjà publiée) ; 14 h 30, USD, inscriptions hebdomadaires au chômage "
            "(dans 5 h 00).") in text  # fmt: skip
    assert "Retail" not in text and "BOJ" not in text and "CPI m/m" not in text
    assert "EUR/USD : 1,10800, +0,73 % depuis hier 18 h (nuit entre 1,09850 et 1,11000)" in text
    assert "Tendance haussière : au-dessus de l'EMA200 journalière" in text
    assert "ton plan n'autorise que des achats aujourd'hui" in text
    # « hier » = mardi, minuit à minuit à Paris, rebâti avec les bougies 1 h
    assert "Niveaux clés : plus haut d'hier 1,10500, plus bas 1,09800" in text
    assert "EMA50 1 h" in text
    assert "objectif d'au moins 2 R" in text and "1 trade ouvert au journal, 2 alertes" in text


def test_briefing_says_what_is_missing_and_follows_the_chart_gap():
    def down(instrument):
        raise MarketUnavailable("Yahoo en panne.")

    text = build([EUR], down, None, PlanRules(), NOW).text()
    assert "Calendrier économique indisponible" in text
    assert "EUR/USD : cours indisponibles ce matin." in text
    shifted = build([EUR], history, [], PlanRules(), NOW, offsets={"EURUSD": 0.01}).text()
    assert "EUR/USD : 1,09800" in shifted and "Aucune annonce forte" in shifted


def test_the_night_starts_at_the_end_of_the_last_trading_day():
    monday = datetime(2026, 10, 12, 7, tzinfo=UTC)
    assert _yesterday_close(monday, 18).strftime("%a %d %H") == "Fri 09 18"
    assert _yesterday_close(NOW, 18).strftime("%d %H") == "06 18"


def make_service(tmp_path, now=NOW, instruments=(), auto=True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    journal = TradeJournal(tmp_path / "t.db")
    store = AlertStore(tmp_path / "alerts.json")
    trading = SimpleNamespace(
        journal=journal, alerts=SimpleNamespace(store=store), rules_path=tmp_path / "r.json",
        current=GOLD, builder=SimpleNamespace(context=SimpleNamespace(events=lambda: ([], None))),
    )  # fmt: skip
    return BriefingService(trading, tmp_path / "state.json", (9, 18), instruments, auto,
                           history, lambda: now, interval=3600), trading  # fmt: skip


def test_instruments_come_from_settings_then_watches_then_the_current_one(tmp_path):
    service, trading = make_service(tmp_path)
    assert service.instruments() == [GOLD]
    trading.alerts.store.add_setup("EURUSD")
    trading.alerts.store.add_level("XAUUSD", 4000, above=False)  # un niveau ne compte pas
    assert service.instruments() == [EUR]
    configured, _ = make_service(tmp_path / "c", instruments=("or", "EUR/USD", "l'or"))
    assert configured.instruments() == [GOLD, EUR]


def test_automatic_briefing_once_per_weekday_during_trading_hours(tmp_path):
    service, trading = make_service(tmp_path)
    trading.journal.open_trade("EURUSD", "achat", 1.1, 1.09)
    said = []
    service.check(said.append)
    service.check(said.append)
    assert len(said) == 1 and "1 trade ouvert au journal" in said[0].text()
    again, _ = make_service(tmp_path)  # redémarrage le même jour : pas de doublon
    assert not again.due()
    for moment in (NOW.replace(hour=5), NOW.replace(hour=17), NOW + timedelta(days=3)):
        assert not make_service(tmp_path / str(moment.hour) / str(moment.day), moment)[0].due()
    assert not make_service(tmp_path / "off", auto=False)[0].due()


def test_tool_and_announcement(tmp_path):
    from friday.app.trading_briefing import start_trading_briefing

    service, _ = make_service(tmp_path)
    result = TradingBriefingTool(service).run("EUR/USD")
    assert result.text.startswith("Dis EXACTEMENT ce texte") and "EUR/USD : 1,10800" in result.text
    assert result.display.data["items"][0]["text"] == "Briefing trading"
    assert "Briefing impossible" in TradingBriefingTool(service).run("zzzz-??").text

    class Voice:
        chimes = 0

        def chime(self):
            Voice.chimes += 1

    done = []
    service.start = lambda on_ready: on_ready(service.build())  # sans attendre le fil
    start_trading_briefing(service, lambda: Voice(), lambda task, r: done.append((task, r)))
    assert Voice.chimes == 1 and done[0][0] == "briefing trading"
    assert done[0][1].text.startswith("(Briefing trading automatique")


def test_briefing_requests_stay_local():
    mode = TradingMode()
    for text in ("briefing trading", "prépare ma journée de trading",
                 "(Briefing trading automatique, début de ta plage de trading.)"):  # fmt: skip
        assert mode.route(text) == "local", text


def test_the_code_launches_the_briefing_with_the_named_instrument():
    from friday.app.prefetch import prefetcher
    from friday.trading.mode import briefing_request

    assert briefing_request("briefing trading") == ""  # ceux des réglages
    assert briefing_request("fais-moi le briefing trading sur l'argent") == "XAGUSD"
    assert briefing_request("prépare ma journée de trading sur l'EUR/USD") == "EURUSD"
    assert briefing_request("quel temps fait-il ?") is None
    assert briefing_request("(Message automatique, pas de l'utilisateur.) briefing trading") is None
    trading = SimpleNamespace(mode=TradingMode(), briefing=object(), job=None)
    prefetch = prefetcher(None, trading, None)
    # hors du mode trading aussi (une routine « briefing trading » à 8 h, T8)…
    assert prefetch("briefing trading sur l'or") == ("trading_briefing", {"instrument": "XAUUSD"})
    assert prefetch("prépare ma journée") is None  # … mais ça, c'est le briefing du matin
    trading.mode.enabled = True
    assert prefetch("briefing trading sur l'or") == ("trading_briefing", {"instrument": "XAUUSD"})
    assert prefetch("prépare ma journée") == ("trading_briefing", {"instrument": ""})
