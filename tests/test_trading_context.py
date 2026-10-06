"""Contexte des analyses (PR D) : annonces, actualités, COT, séances, plan de trading."""

from datetime import UTC, datetime, timedelta, timezone

from friday.trading import calendar, cot, news, sessions
from friday.trading.analyst import RULES
from friday.trading.calendar import Event, SourceUnavailable
from friday.trading.context_builder import ContextBuilder
from friday.trading.context_sources import ContextSources, load_plan, save_plan
from friday.trading.instruments import by_symbol
from friday.trading.news import Headline

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)  # un mercredi
EDT = timezone(timedelta(hours=-4))


def event(hours, currency="USD", impact="High", title="Non-Farm Payrolls"):
    return Event(NOW + timedelta(hours=hours), currency, title, impact, "150K", "142K")


def test_calendar_keeps_the_instruments_important_announcements():
    events = [
        event(2), event(5, "EUR", "Medium", "ECB Lagarde Speaks"), event(3, "JPY"),
        event(1, impact="Low"), event(-20), event(60), event(4, "All", "Medium", "OPEC"),
    ]  # fmt: skip
    kept = calendar.relevant(events, ("EUR", "USD"), NOW)
    assert [e.title for e in kept] == ["Non-Farm Payrolls", "OPEC", "ECB Lagarde Speaks"]
    text = calendar.text(kept, NOW)
    assert "mercredi 07/10 16:00 · USD · impact fort · Non-Farm Payrolls" in text  # heure de Paris
    assert "prévision 150K, précédent 142K" in text and "à venir" in text
    assert "Aucune annonce" in calendar.text([], NOW)


def test_news_keeps_recent_headlines_about_the_instrument():
    items = [
        Headline(NOW - timedelta(hours=1), "Gold rebounds as yields fall", "XAU/USD up."),
        Headline(NOW - timedelta(hours=2), "EUR/USD steadies", "The Euro holds 1.1250."),
        Headline(NOW - timedelta(hours=30), "Gold old news", "old"),
        Headline(NOW - timedelta(hours=1), "Oil slips", "WTI down."),
    ]
    gold = news.relevant(items, by_symbol("XAUUSD"), NOW)
    assert [h.title for h in gold] == ["Gold rebounds as yields fall"]
    euro = news.relevant(items, by_symbol("EURUSD"), NOW)
    assert "EUR/USD steadies" in [h.title for h in euro]
    peso = [Headline(NOW, "Mexican Peso gains as US yields fall", "against the US Dollar")]
    assert news.relevant(peso, by_symbol("EURUSD"), NOW) == []  # « dollar » ne suffit pas
    assert "titres et résumés de tiers" in news.text(gold)


def cot_row(name, longs, shorts, change_long, change_short):
    row = [name, "260929", "2026-09-29"] + ["0"] * 37
    row[cot.LONG], row[cot.SHORT] = str(longs), str(shorts)
    row[cot.CHANGE_LONG], row[cot.CHANGE_SHORT] = str(change_long), str(change_short)
    return row


def test_cot_positioning_is_summarised_locally():
    rows = [
        cot_row("GOLD - COMMODITY EXCHANGE INC.", 249736, 31104, -4246, 2975),
        cot_row("EURO FX - CHICAGO MERCANTILE EXCHANGE", 238183, 301439, 17475, 28397),
    ]
    gold = cot.positioning(rows, "GOLD - ")
    assert gold.net == 218632 and gold.change_net == -7221 and gold.market == "or"
    assert cot.markets_for(by_symbol("EURUSD")) == ["EURO FX - ", "USD INDEX - "]
    text = cot.text([cot.positioning(rows, "EURO FX - ")])
    assert "euro : nets vendeurs 63 256 (achats 238 183, ventes 301 439)" in text
    assert "-10 922" in text
    assert "Pas de marché COT" in cot.text([])


def test_sessions_follow_each_place_and_the_weekend():
    london_morning = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)  # 10 h à Londres (heure d'été)
    assert "Londres" in sessions.open_sessions(london_morning)
    overlap = datetime(2026, 10, 7, 13, 30, tzinfo=UTC)  # Londres + New York
    assert {"Londres", "New York"} <= set(sessions.open_sessions(overlap))
    assert "chevauchement" in sessions.text(overlap)
    saturday = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    assert sessions.open_sessions(saturday) == [] and "fermé" in sessions.text(saturday)
    friday_night = datetime(2026, 10, 9, 18, 0, tzinfo=EDT)  # vendredi 18 h à New York
    assert sessions.forex_closed(friday_night)
    assert "mercredi 07/10" in sessions.text(NOW) and "Paris" in sessions.text(NOW)


def failing():
    raise SourceUnavailable("Calendrier économique indisponible (hors ligne).")


def test_one_source_down_does_not_block_the_others(tmp_path):
    plan = tmp_path / "plan.txt"
    save_plan(plan, "Risque 1 % par trade, compte de 5 000 €, pas de trade avant le NFP.")
    sources = ContextSources(plan, events=failing, headlines=lambda: [], cot_rows=lambda: [],
                             now=lambda: NOW)  # fmt: skip
    blocks, notes = sources.blocks(by_symbol("EURUSD"))
    assert [b.kind for b in blocks] == ["actualites", "positionnement", "seances", "plan"]
    assert "Calendrier économique indisponible" in notes[0] and "sans ce bloc" in notes[0]
    packet = ContextBuilder(context=sources).build("EUR/USD ?", instrument=by_symbol("EURUSD"))
    plan_item = next(i for i in packet.items if i.kind == "plan")
    assert "5 000" not in plan_item.text and "montant" in packet.masked  # plan masqué
    assert "Risque 1 % par trade" in plan_item.text
    assert packet.notes == notes


def test_plan_storage_and_editor(tmp_path):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.trading_plan import TradingPlanRow

    QApplication.instance() or QApplication([])
    path = tmp_path / "plan.txt"
    assert load_plan(path) == ""
    row = TradingPlanRow(path)
    row.editor.setPlainText("Swing 4 h, 1 % de risque.")
    row.save()
    assert load_plan(path) == "Swing 4 h, 1 % de risque." and "enregistré" in row.status.text()
    assert not TradingPlanRow(None).editor.isEnabled()


def test_claude_is_asked_for_scenarios_and_to_respect_the_plan():
    assert "scénario haussier et un baissier" in RULES and "invaliderait" in RULES
    assert "SES règles" in RULES and "fort impact proche" in RULES


def test_disk_cache_spares_free_sources_and_survives_a_block(tmp_path):
    import os
    import time

    import httpx
    import pytest

    from friday.trading.cache import age_note, cached_text

    path = tmp_path / "cache" / "ff.json"
    calls = []

    def download():
        calls.append(1)
        return "[]"

    assert cached_text(path, 3600, download) == ("[]", None) and len(calls) == 1
    assert cached_text(path, 3600, download) == ("[]", None) and len(calls) == 1  # en cache
    old = time.time() - 2 * 3600
    os.utime(path, (old, old))

    def blocked():
        request = httpx.Request("GET", "https://x")
        raise httpx.HTTPStatusError("429", request=request,
                                    response=httpx.Response(429, request=request))  # fmt: skip

    text, age = cached_text(path, 3600, blocked)  # vieille copie de secours
    assert text == "[]" and 7000 < age < 7400
    assert "dernière version connue (il y a 2 h)" in age_note("Calendrier économique", age)
    with pytest.raises(httpx.HTTPStatusError):
        cached_text(tmp_path / "rien.json", 3600, blocked)  # aucune copie : l'erreur remonte
    with pytest.raises(SourceUnavailable, match="code 429 : trop de demandes"):
        calendar.load(tmp_path / "vide.json", get=lambda *a, **k: blocked())
