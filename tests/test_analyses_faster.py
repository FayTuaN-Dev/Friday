"""Analyses plus rapides et mieux nourries (T6) : données préparées en avance, mémoire des
analyses de Claude, bibliothèque enrichie par l'instrument, données de la zone euro."""

import json
import sqlite3
import threading
from types import SimpleNamespace

import httpx
import pytest

from friday.library.store import Hit
from friday.tools.analyses import PastAnalysesTool
from friday.trading import euro_data
from friday.trading.alerts.store import AlertStore
from friday.trading.analysis_memory import past_text
from friday.trading.calendar import SourceUnavailable
from friday.trading.context_builder import ContextBuilder
from friday.trading.instruments import by_symbol
from friday.trading.journal import TradeJournal
from friday.trading.market import MarketUnavailable
from friday.trading.mode import TradingMode
from friday.trading.warm import Warm, start_warming

GOLD = by_symbol("XAUUSD")
EUR = by_symbol("EURUSD")


# --- données préparées en avance --------------------------------------------------------------


def test_warm_keeps_values_for_a_while_but_never_errors():
    clock = [0.0]
    calls = []

    def fetch(name):
        calls.append(name)
        if name == "panne":
            raise RuntimeError("Yahoo")
        return f"{name}-{len(calls)}"

    warm = Warm(fresh=90, clock=lambda: clock[0])
    cached = warm.wrap("cours", fetch)
    assert cached("or") == cached("or") == "or-1" and cached("eur") == "eur-2"
    clock[0] = 91
    assert cached("or") == "or-3"  # périmée : relue
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cached("panne")
    assert calls.count("panne") == 2  # une erreur n'est jamais gardée


def test_warming_prepares_current_and_watched_instruments_in_trading_mode_only(tmp_path):
    store = AlertStore(tmp_path / "a.json")
    store.add_setup("EURUSD")
    store.add_setup("XAUUSD")
    trading = SimpleNamespace(mode=TradingMode(), current=GOLD,
                              alerts=SimpleNamespace(store=store))  # fmt: skip
    seen, done = [], threading.Event()

    def task(instrument):
        seen.append(instrument.symbol)
        if len(seen) >= 2:
            done.set()

    stop = start_warming(trading, task, interval=0.01)
    assert not done.wait(0.1) and seen == []  # mode trading éteint : rien
    trading.mode.enabled = True
    assert done.wait(2)
    stop.set()
    assert seen[:2] == ["XAUUSD", "EURUSD"]  # l'instrument courant d'abord, sans doublon


# --- données de la zone euro --------------------------------------------------------------------

HICP = json.dumps(
    {
        "dimension": {"time": {"category": {"index": {"2026-07": 0, "2026-08": 1, "2026-09": 2}}}},
        "value": {"0": 2.9, "1": 3.2, "2": 3.8},
    }
)
UNEMPLOYMENT = "KEY,TIME_PERIOD,OBS_VALUE\nx,2026-07,6.5\nx,2026-08,6.4\n"
RATE = "KEY,TIME_PERIOD,OBS_VALUE\nx,2026-06-17,2.25\nx,2026-09-16,2.5\n"


def fake_get(fail=()):
    def get(url, timeout=None):
        request = httpx.Request("GET", url)
        if any(part in url for part in fail):
            return httpx.Response(503, request=request)
        body = HICP if "eurostat" in url else UNEMPLOYMENT if "LFSI" in url else RATE
        return httpx.Response(200, text=body, request=request)

    return get


def test_euro_area_figures_in_french(tmp_path):
    text = euro_data.text(tmp_path, fake_get())
    assert text == ("Zone euro (sources officielles) : inflation 3,8 % sur un an en septembre "
                    "2026 (Eurostat), après 3,2 % en août, 2,9 % en juillet ; chômage 6,4 % en "
                    "août 2026 (BCE) ; taux de dépôt de la BCE 2,5 % depuis le 16/09/2026 "
                    "(avant : 2,25 %).")  # fmt: skip
    assert (tmp_path / "eurostat_hicp.json").is_file()  # gardées 12 h
    assert euro_data.text(tmp_path, fake_get(fail=("eurostat", "LFSI", "FM/"))) == text


def test_one_euro_source_down_is_said_and_all_down_is_unavailable(tmp_path):
    partial = euro_data.text(tmp_path / "p", fake_get(fail=("LFSI",)))
    assert "ecb_unemployment indisponible : code 503" in partial and "inflation 3,8 %" in partial
    with pytest.raises(SourceUnavailable):
        euro_data.text(tmp_path / "n", fake_get(fail=("eurostat", "LFSI", "FM/")))


# --- bibliothèque : le sujet, puis l'instrument ----------------------------------------------


class Library:
    def __init__(self):
        self.asked = []

    def search(self, query, limit=4, close_to_best=0.12):
        self.asked.append(query)
        if query.startswith("l'or"):
            return [hit(1, "Le double sommet…"), hit(7, "L'or, valeur refuge.")][:limit]
        return [hit(1, "Le double sommet…")]


def hit(i, text):
    return Hit(i, f"doc{i}.md", f"C:\\data\\doc{i}.md", None, text)


def test_library_search_adds_passages_about_the_instrument():
    library = Library()
    packet = ContextBuilder(library).build("que penses-tu de ce double sommet ?", instrument=GOLD)
    texts = [i.text for i in packet.items if i.kind == "extrait"]
    assert texts == ["Le double sommet…", "L'or, valeur refuge."]  # sujet d'abord, sans doublon
    assert library.asked[1] == "l'or (XAUUSD) : métaux précieux, matières premières"
    ContextBuilder(library).build("le RSI ?")
    assert len(library.asked) == 3  # sans instrument : une seule recherche


# --- mémoire des analyses ----------------------------------------------------------------------


def test_an_old_journal_learns_to_remember_analyses(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE sent (id INTEGER PRIMARY KEY, sent_at TEXT NOT NULL, question TEXT "
               "NOT NULL, content TEXT NOT NULL, chars INTEGER NOT NULL, images TEXT NOT NULL "
               "DEFAULT '', answer TEXT)")  # fmt: skip
    db.executemany("INSERT INTO sent (sent_at, question, content, chars, answer) VALUES "
                   "(?, ?, 'c', 1, ?)", [
                       ("2026-10-06T10:00:00", "Et le cours de l'argent ?", "Prudence."),
                       ("2026-10-06T11:00:00", "Le RSI, c'est quoi ?", "Un indicateur."),
                   ])  # fmt: skip
    db.commit()
    db.close()
    journal = TradeJournal(path)
    sent = journal.log_sent("L'or ?", "contenu", instrument="XAUUSD", price=4100.0)
    journal.log_answer(sent, "Scénario baissier sous 4 080.")
    journal.log_sent("Sans réponse", "contenu", instrument="XAUUSD")
    journal.log_answer(journal.log_sent("EUR ?", "c", instrument="EURUSD"), "Haussier.")
    (gold,) = journal.analyses("XAUUSD")
    assert (gold.question, gold.answer, gold.price) == ("L'or ?", "Scénario baissier sous 4 080.",
                                                        4100.0)  # fmt: skip
    assert [a.instrument for a in journal.analyses()] == ["EURUSD", "XAUUSD", "", "XAGUSD"]
    assert journal.analyses("XAGUSD")[0].price is None  # ancienne : instrument retrouvé


def test_past_analyses_join_the_packet_with_the_move_since(tmp_path):
    journal = TradeJournal(tmp_path / "t.db")
    journal.log_answer(journal.log_sent("L'or ?", "c", instrument="XAUUSD", price=4000.0),
                       "Baissier sous 3 980. " + "x" * 900)  # fmt: skip
    market = lambda i: SimpleNamespace(quote=SimpleNamespace(price=4040.0),  # noqa: E731
                                       text=lambda chart=None: "marché")  # fmt: skip
    packet = ContextBuilder(None, journal, market=market).build("et l'or ?", instrument=GOLD)
    (memory,) = [i for i in packet.items if i.kind == "analyses_passees"]
    assert "depuis, le cours a fait +1,00 %" in memory.text and "Baissier sous 3 980" in memory.text
    assert memory.text.endswith("… »") and len(memory.text) < 900  # réponse raccourcie
    assert (packet.instrument, packet.price) == ("XAUUSD", 4040.0)
    eur = ContextBuilder(None, journal, market=market).build("et l'euro ?", instrument=EUR)
    assert not [i for i in eur.items if i.kind == "analyses_passees"]  # autre instrument
    assert past_text([], 1.0) is None


def test_analysis_is_logged_with_its_instrument_and_price(tmp_path):
    from test_trading import FakeJob, StubLibrary, wait_for

    from friday.tools.trading_analysis import TradingAnalysisTool

    journal = TradeJournal(tmp_path / "t.db")
    market = lambda i: SimpleNamespace(quote=SimpleNamespace(price=4100.0),  # noqa: E731
                                       text=lambda chart=None: "marché")  # fmt: skip
    builder = ContextBuilder(StubLibrary([]), journal, market=market)
    done = []
    tool = TradingAnalysisTool(builder, FakeJob(tmp_path), journal, lambda t, r: done.append(r),
                               lambda q: GOLD)  # fmt: skip
    tool.confirmation({"question": "que penses-tu de l'or ?"})
    tool.preview({}).approved = True
    tool.run("que penses-tu de l'or ?")
    wait_for(done)
    (analysis,) = journal.analyses("XAUUSD")
    assert analysis.price == 4100.0


def test_past_analyses_tool(tmp_path):
    journal = TradeJournal(tmp_path / "t.db")
    tool = PastAnalysesTool(journal, lambda instrument: 4040.0)
    assert "Aucune analyse" in tool.run().text
    journal.log_answer(journal.log_sent("L'or ?", "c", instrument="XAUUSD", price=4000.0), "Bas.")
    result = tool.run("or")
    assert "« Ta dernière analyse : le " in result.text
    assert "l'or ; depuis, le cours a fait +1,00 %." in result.text
    assert result.display.data["items"][0]["meta"] == "« L'or ? » — Bas."

    def down(instrument):
        raise MarketUnavailable("Yahoo")

    assert "l'or." in PastAnalysesTool(journal, down).run().text  # sans comparaison
    assert "Demande lequel" in tool.run("zzzz-??").text


def test_memory_requests_stay_local():
    mode = TradingMode()
    assert mode.route("mes dernières analyses") == "local"
    assert mode.route("tes analyses sur l'or ont-elles marché ?") == "local"
