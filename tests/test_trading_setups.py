"""Page Trading → « Setups » : le carnet de la surveillance, l'avis de Claude et le bilan."""

import json

from PySide6.QtWidgets import QApplication

from friday.trading.alerts.setup_log import PENDING, SetupLog
from friday.ui.desktop.trading.setups_tab import SetupsView, review_text, row_values

app = QApplication.instance() or QApplication([])


def entry(n, avis=None, result=None, **more):
    return {"id": n, "symbol": "XAUUSD", "side": "achat", "bar": f"2026-10-{n:02d}T10:00:00",
            "close": 4100.0, "stop": 4080.0, "target": 4140.0, "trail": None,
            "strategy": "mon_plan", "label": "Mon plan", "unit": "heure",
            "text": f"Alerte setup n°{n}.", "seen": f"2026-10-{n:02d}T11:00:00",
            "announced": True, "avis": avis, "raison": "Plan respecté." if avis else "",
            "closed": "2026-10-20T15:00:00" if result is not None else None,
            "result_r": result, **more}  # fmt: skip


def notebook(tmp_path, entries):
    path = tmp_path / "setups.json"
    path.write_text(json.dumps(entries), "utf-8")
    return SetupLog(path)


def test_table_lists_setups_newest_first_with_claude_verdict(tmp_path):
    setups = notebook(tmp_path, [entry(1, "oui", 2.0), entry(2, "non", -1.0), entry(3, PENDING)])
    view = SetupsView(setups)
    assert view.table.rowCount() == 3
    cells = [view.table.item(0, c).text() for c in range(view.table.columnCount())]
    assert cells[0] == "03/10 11:00" and cells[-2:] == ["en attente", "en cours"]
    assert view.table.item(2, 7).text() == "OUI" and view.table.item(2, 8).text() == "+2.00 R"
    assert view.table.item(2, 7).toolTip() == "Plan respecté."
    view.table.selectRow(2)
    assert "Alerte setup n°1." in view.detail.text() and "OUI" in view.detail.text()
    view.filter.setCurrentText("Claude a dit NON")
    assert view.table.rowCount() == 1 and view.table.item(0, 7).text() == "NON"


def test_new_setup_appears_and_review_compares_verdicts(tmp_path):
    setups = notebook(tmp_path, [entry(1, "oui", 2.0)])
    view = SetupsView(setups)
    assert view.summary.text() == "1 setup(s) terminé(s) : +2,00 R par trade"
    assert "Claude a dit OUI : 1 trade" in view.review.text()
    assert "trop tôt pour conclure" in view.review.text()
    setups._entries.append(entry(2, "non", -1.0))  # la surveillance en note un autre
    view.refresh()
    assert view.table.rowCount() == 2 and "Claude a dit NON : 1 trade" in view.review.text()


def test_empty_or_disabled_notebook_explains_how_to_fill_it(tmp_path):
    assert "surveille tous les marchés" in SetupsView(None).summary.text()
    assert review_text([entry(1)]) == ("1 setup(s) noté(s), aucun terminé · 1 en cours", "")
    trailing = row_values(entry(1, target=None, trail=20))
    assert trailing[6] == "suiveuse (20)" and trailing[4] == "4100.00"


def test_curves_share_one_axis_and_bars_rank_markets(tmp_path):
    from friday.trading.alerts.review import curves, totals_by

    entries = [entry(1, "oui", 2.0), entry(2, "non", -1.0, symbol="EURUSD"), entry(3, None, 1.5),
               entry(4, PENDING)]  # fmt: skip
    entries[0]["closed"] = "2026-10-21T10:00:00"  # sorti après les deux autres
    points = curves(entries)
    assert [e["id"] for e, _ in points] == [2, 3, 1]  # dans l'ordre des sorties
    assert [totals for _, totals in points] == [[-1.0, 0.0, -1.0], [0.5, 0.0, -1.0],
                                                [2.5, 2.0, -1.0]]  # fmt: skip
    assert totals_by(entries, lambda e: e["symbol"]) == [("XAUUSD", 2, 3.5), ("EURUSD", 1, -1.0)]


def test_charts_hidden_until_a_setup_is_closed(tmp_path):
    view = SetupsView(notebook(tmp_path, [entry(1, PENDING)]))
    assert view.charts.isHidden()
    view.setups._entries.append(entry(2, "oui", 2.0))
    view.refresh()
    assert not view.charts.isHidden() and len(view.charts.curves.points) == 1
    assert view.charts.markets.rows == [("l'or", 1, 2.0)]
    view.resize(600, 900)
    view.grab()  # le dessin ne plante pas
