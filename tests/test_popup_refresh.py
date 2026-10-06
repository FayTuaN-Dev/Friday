from fakes import SETTINGS
from PySide6.QtWidgets import QApplication

from friday.tools.base import Display, Tool, ToolBox, ToolResult

app = QApplication.instance() or QApplication([])


def items(title, *texts, key="briefing", refresh=False):
    return Display("items", title, {"icon": "☀️", "items": [{"text": t} for t in texts]},
                   key=key, refresh=refresh)  # fmt: skip


def make_window(tmp_path):
    from test_desktop import StubAssistant

    from friday.ui.desktop.main_window import MainWindow

    return MainWindow(SETTINGS, assistant=StubAssistant(), preferences_path=tmp_path / "i.json")


def texts(popup):
    from PySide6.QtWidgets import QLabel

    return [label.text() for label in popup.findChildren(QLabel)]


def test_open_list_is_updated_in_place(tmp_path):
    w = make_window(tmp_path)
    first = w.popups.show(items("Briefing", "Météo"))
    first.move(321, 123)
    updated = w.popups.show(items("Briefing", "Météo", "Agenda", refresh=True))
    app.processEvents()
    assert len(w.popups.popups) == 1 and w.popups.popups[0] is updated
    assert updated.pos().x() == 321 and "Agenda" in texts(updated)  # même place, contenu à jour
    w.close()


def test_refresh_never_opens_a_new_popup(tmp_path):
    w = make_window(tmp_path)
    assert w.popups.show(items("Briefing", "Météo", refresh=True)) is None
    assert w.popups.popups == []
    w.popups.show(items("Notes", "lait", key="notes:courses"))
    assert w.popups.show(items("Briefing", "Météo", refresh=True)) is None  # autre liste
    assert len(w.popups.popups) == 1
    w.close()


def test_unknown_arguments_are_ignored():
    class Strict(Tool):
        name = "strict"
        description = "test"
        parameters = {"action": {"type": "string"}}

        def run(self, action: str) -> ToolResult:
            return ToolResult(f"fait : {action}")

    result = ToolBox([Strict()]).run("strict", {"action": "add", "reason": "ajout"})
    assert result.text == "fait : add"  # « reason » inventé : ignoré au lieu de planter


def test_list_tools_refresh_their_popup(tmp_path):
    from friday.agenda.store import AgendaStore
    from friday.tools.notes import AddNoteTool, ListNotesTool, RemoveNoteTool

    store = AgendaStore(tmp_path / "agenda.db")
    shown = ListNotesTool(store).run("courses") if store.notes("courses") else None
    assert shown is None
    added = AddNoteTool(store).run("lait", "courses")
    assert added.display.refresh and added.display.key == "notes:courses"
    assert ListNotesTool(store).run("courses").display.key == "notes:courses"
    removed = RemoveNoteTool(store).run(store.notes("courses")[0].id)
    assert removed.display.refresh and removed.display.data["items"] == []
