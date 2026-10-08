"""Notifications Windows (F3) : la bulle dit la phrase de l'annonce, seulement si Friday n'est
pas au premier plan ; un clic la ramène devant."""

from PySide6.QtWidgets import QApplication, QWidget

from friday.app.notification import notification
from friday.tools.base import ToolResult
from friday.ui.desktop.icons import icon
from friday.ui.desktop.notifier import Notifier

app = QApplication.instance() or QApplication([])


def test_the_bubble_says_the_announced_sentence():
    alert = notification("alerte", ToolResult(
        "ALERTE DE TRADING. Dis EXACTEMENT : « Alerte setup « la cassure de range » sur l'or : "
        "achat. » N'ajoute aucun conseil."))  # fmt: skip
    assert alert.kind == "notification" and alert.title == "🔔 Alerte de trading"
    assert alert.data["text"] == "Alerte setup « la cassure de range » sur l'or : achat."
    claude = notification("que penses-tu de l'or ?", ToolResult("Réponse de Claude : …"))
    assert claude.title == "💬 Réponse de Claude prête"
    assert claude.data["text"] == "« que penses-tu de l'or ? »"
    long = notification("rappel", ToolResult("RAPPEL : " + "appeler le garage " * 30))
    assert long.title == "⏰ Rappel" and long.data["text"].endswith("…")
    assert len(long.data["text"]) <= 200


def test_only_when_friday_is_not_in_front():
    window = QWidget()
    notifier = Notifier(window, icon("pulse", "#8a5cff", 32))
    shown = notification("rappel", ToolResult("Dis EXACTEMENT : « Rappel : sortir le chien. »"))
    notifier.in_front = lambda: True
    assert not notifier.notify(shown) and notifier.sent == []
    notifier.in_front = lambda: False  # réduite, ou derrière TradingView
    assert notifier.notify(shown)
    assert notifier.sent == [("⏰ Rappel", "Rappel : sortir le chien.")]
    window.showMinimized()
    notifier.bring_back()
    assert not window.isMinimized()
    window.close()
