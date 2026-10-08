"""Limites Claude à l'écran (F7) : le relais de la ligne d'état de Claude Code garde session et
semaine ; Friday affiche le restant, la remise à zéro, l'âge des chiffres."""

import json

from friday.app.claude_limits import read
from friday.claude_status import install, relay

NOW = 1_791_459_833.0
FEED = json.dumps({"model": {"id": "x"}, "rate_limits": {
    "five_hour": {"used_percentage": 85, "resets_at": NOW + 2 * 3600 + 40 * 60},
    "seven_day": {"used_percentage": 94.4, "reset_at": NOW + 3 * 86400}}})  # fmt: skip


def test_relay_keeps_the_figures_and_writes_a_short_line(tmp_path):
    target = tmp_path / "claude_limits.json"
    line = relay(FEED, target, now=NOW)
    assert line == "Claude : session 15 % restants · semaine 6 % restants"
    saved = json.loads(target.read_text("utf-8"))
    assert saved["five_hour"]["used"] == 85 and saved["seven_day"]["resets_at"] == NOW + 3 * 86400
    assert relay("{}", tmp_path / "rien.json") == "Friday : limites Claude indisponibles"
    assert relay("pas du json", tmp_path / "rien.json").startswith("Friday")
    assert not (tmp_path / "rien.json").exists()


def test_friday_reads_what_is_left_and_when_it_resets(tmp_path):
    target = tmp_path / "claude_limits.json"
    relay(FEED, target, now=NOW)
    session, week = read(target, NOW).windows
    assert (session.label, round(session.left)) == ("Session Claude", 15)
    assert session.reset_text(NOW) == "remise à zéro dans 2 h 40"
    assert week.reset_text(NOW).startswith("remise à zéro ") and " à " in week.reset_text(NOW)
    assert read(target, NOW).age_text(NOW) == ""
    later = read(target, NOW + 3 * 3600)  # la session est remise à zéro, la semaine non
    assert later.windows[0].left == 100 and round(later.windows[1].left) == 6
    assert later.age_text(NOW + 3 * 3600).startswith("chiffres d'il y a 3 h 00")
    assert read(tmp_path / "absent.json") is None


def test_plugging_into_claude_code_keeps_a_copy_and_never_overwrites(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"theme": "dark"}), "utf-8")
    assert install(settings).startswith("Branché")
    data = json.loads(settings.read_text("utf-8"))
    assert data["theme"] == "dark" and "friday.claude_status" in data["statusLine"]["command"]
    assert json.loads((tmp_path / "settings.json.avant-friday").read_text("utf-8")) == {
        "theme": "dark"}  # fmt: skip
    assert install(settings) == "Déjà branché."
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"statusLine": {"type": "command", "command": "mon-script"}}))
    assert "je n'y touche pas" in install(other)
    assert json.loads(other.read_text())["statusLine"]["command"] == "mon-script"


def test_the_bars_show_what_is_left(tmp_path):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.widgets.claude_limits import HOW, ClaudeLimits

    QApplication.instance() or QApplication([])
    target = tmp_path / "claude_limits.json"
    empty = ClaudeLimits(target, clock=lambda: NOW)
    assert empty.note.text() == HOW
    relay(FEED, target, now=NOW)
    panel = ClaudeLimits(target, clock=lambda: NOW)
    session, week = panel.rows
    assert (session.name.text(), session.value.text()) == ("SESSION", "15 %")
    assert session.bar.value() == 15 and week.name.text() == "SEMAINE"
    assert session.detail.text() == "restants · remise à zéro dans 2 h 40"
    assert session.value.property("low") is True  # sous 20 % : couleur d'alerte
