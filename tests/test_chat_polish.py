from datetime import datetime

from fakes import RecordingListener
from PySide6.QtWidgets import QApplication

from friday.app.reply import Reply
from friday.brain.events import ThinkingStarted, ToolFinished, ToolStarted
from friday.tools.base import Tool, ToolBox, ToolResult
from friday.ui.desktop.widgets.chat import ChatView
from friday.ui.desktop.widgets.confirm_card import ConfirmCard
from friday.ui.desktop.widgets.tool_chip import ToolChip, duration

app = QApplication.instance() or QApplication([])


def test_tool_chip_spins_then_shows_outcome_and_duration():
    chip = ToolChip("🔎 Recherche : météo Lyon")
    assert chip.running and chip.property("state") == "running"
    chip.finish(ok=False)
    assert chip.mark.text() == "✗" and chip.property("state") == "failed"
    assert chip.time.text().endswith("s")
    chip.finish(ok=True)  # déjà fini : rien ne change
    assert chip.mark.text() == "✗"
    assert duration(1.234) == "1,2 s" and duration(42) == "42 s" and duration(95) == "1 min 35"


def test_chat_finishes_tools_in_order_and_stops_spinners_at_the_end():
    chat = ChatView()
    chat.add_tool("A")
    chat.add_tool("B")
    chat.finish_tool(True)
    first, second = chat.findChildren(ToolChip)
    assert not first.running and second.running
    chat.end_reply(interrupted=True)
    assert not second.running and second.time.text() == "interrompu"


def test_messages_carry_their_time_and_a_new_day_gets_a_separator():
    chat = ChatView()
    clock = [datetime(2026, 10, 13, 23, 58)]
    chat.clock = lambda: clock[0]
    chat.add_user("Bonsoir", False)
    assert chat._bubbles[0].findChildren(type(chat.welcome.date))[0].text() == "Vous · 23:58"
    clock[0] = datetime(2026, 10, 14, 0, 3)
    chat.add_user("Toujours là ?", True)
    labels = [w.text() for w in chat.widget().findChildren(type(chat.welcome.date))]
    assert "— Mercredi 14 octobre —" in labels
    assert "Vous · à la voix · 00:03" in labels


def test_confirmation_card_says_what_happened():
    chat = ChatView()
    card = chat.add_confirmation("Je lance ?", 60)
    chat.add_tool("🤖 Claude")  # un outil démarre : c'était un « oui » (à la voix)
    assert card.closed and card.outcome.text() == "✓ Lancé"
    other = chat.add_confirmation("Je supprime ?", 60)
    chat.end_reply(interrupted=False)
    assert other.closed and "Rien" in other.outcome.text()


def test_confirmation_card_runs_out_of_time():
    card = ConfirmCard("Je lance ?", seconds=1)
    answers = []
    card.answered.connect(answers.append)
    card._start -= 2  # le délai est passé
    card._tick()
    assert card.closed and "Délai" in card.outcome.text() and answers == []
    assert card.bar.value() == 0


class Broken(Tool):
    name = "broken"
    description = "Plante."
    parameters = {}

    def run(self) -> ToolResult:
        raise RuntimeError("boum")


def test_a_failing_tool_is_marked_failed():
    assert not ToolBox([Broken()]).run("broken", {}).ok
    assert not ToolBox([]).run("absent", {}).ok


def test_reply_reports_tool_outcomes_and_closes_the_thinking_chip():
    import threading

    listener = RecordingListener()
    events = [ThinkingStarted(), ToolStarted("web", {}, "🔎 Recherche"),
              ToolFinished("web", ToolResult("rien", ok=False)), "Désolé."]  # fmt: skip
    Reply(listener, None, threading.Event()).run(iter(events))
    assert listener.of("tool") == [("🧠 Réflexion approfondie",), ("🔎 Recherche",)]
    assert listener.of("tool_done") == [(True,), (False,)]
