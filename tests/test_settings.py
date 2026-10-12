from types import SimpleNamespace

import pytest
from fakes import SETTINGS
from PySide6.QtWidgets import QApplication

from friday.core import env_file
from friday.core.settings_schema import SECTIONS, Field
from friday.ui.desktop.settings.form_page import FormPage, make_control
from friday.ui.desktop.widgets.toggle import Toggle

app = QApplication.instance() or QApplication([])


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("# Mon nom\nFRIDAY_USER_NAME=Monsieur\n\n# Voix\nTTS_SPEED=1.0\n", "utf-8")
    monkeypatch.setattr(env_file, "ENV_PATH", path)  # jamais le vrai .env
    return path


def test_update_env_keeps_comments_and_adds_missing_keys(env):
    env_file.update_env({"FRIDAY_USER_NAME": "Valentin", "HOME_CITY": "Les Herbiers"})
    text = env.read_text("utf-8")
    assert "# Mon nom" in text and "# Voix" in text and "TTS_SPEED=1.0" in text
    assert "FRIDAY_USER_NAME=Valentin" in text and "HOME_CITY=Les Herbiers" in text
    assert env_file.read_env()["HOME_CITY"] == "Les Herbiers"


def test_controls_follow_field_kinds():
    assert isinstance(make_control(Field("A", "a", "bool"), "true"), Toggle)
    speed = make_control(Field("B", "b", "float", "1.0", minimum=0.6, maximum=1.6, step=0.05), "")
    assert speed.value() == 1.0
    combo = make_control(Field("C", "c", "choice", options=lambda: [("x", "X")]), "Auna")
    assert combo.currentData() == "Auna"  # valeur écrite à la main : gardée


def test_form_reports_only_changed_values():
    general = next(s for s in SECTIONS if s.name == "Général")
    page = FormPage(general, {"FRIDAY_USER_NAME": "Monsieur"})
    assert page.changes() == {}
    name, _ = page._controls["FRIDAY_USER_NAME"]
    name.setText("Valentin")
    assert page.changes() == {"FRIDAY_USER_NAME": "Valentin"}
    page.commit()
    assert page.changes() == {}


def test_settings_window_saves_to_env_and_offers_restart(env, tmp_path):
    from test_desktop import StubAssistant

    from friday.ui.desktop.main_window import MainWindow
    from friday.ui.desktop.settings.window import SettingsWindow

    assistant = StubAssistant()
    assistant.components = SimpleNamespace(briefing=None, google=None)
    w = MainWindow(SETTINGS, assistant=assistant, preferences_path=tmp_path / "i.json")
    window = SettingsWindow(w)
    assert not window.save() and window.restart_button.isHidden()  # rien de changé
    general = window.forms[0]
    general._controls["FRIDAY_USER_NAME"][0].setText("Valentin")
    assert window.save()
    assert "FRIDAY_USER_NAME=Valentin" in env.read_text("utf-8")
    assert not window.restart_button.isHidden()
    window.close()
    w.close()


def test_open_settings_by_voice_opens_the_window(env, tmp_path):
    from test_desktop import StubAssistant

    from friday.tools.popups import OpenSettingsTool
    from friday.ui.desktop.main_window import MainWindow

    assistant = StubAssistant()
    assistant.components = SimpleNamespace(briefing=None, google=None)
    w = MainWindow(SETTINGS, assistant=assistant, preferences_path=tmp_path / "i.json")
    w.bridge.on_display(OpenSettingsTool().run().display)
    app.processEvents()
    assert w.settings_window is not None and w.popups.popups == []
    w.close()


def test_briefing_page_edits_live(tmp_path):
    from friday.briefing import Briefing, BriefingConfig, Section, Sources
    from friday.ui.desktop.settings.briefing_page import BriefingPage

    path = tmp_path / "b.json"
    BriefingConfig(sections=[Section("meteo"), Section("rappels")]).save(path)
    briefing = Briefing(path, Sources())
    page = BriefingPage(briefing)
    page._remove(briefing.config.sections[1])
    page.kind.setCurrentIndex(page.kind.findData("actualites"))
    page.value.setText("tech")
    page._add()
    page.end.setValue(10)
    config = briefing.config
    assert [s.kind for s in config.sections] == ["meteo", "actualites"] and config.end_hour == 10


def test_settings_can_be_reopened_after_closing(env, tmp_path):
    from test_desktop import StubAssistant

    from friday.ui.desktop.main_window import MainWindow

    assistant = StubAssistant()
    assistant.components = SimpleNamespace(briefing=None, google=None)
    w = MainWindow(SETTINGS, assistant=assistant, preferences_path=tmp_path / "i.json")
    w.open_settings()
    first = w.settings_window
    first.close()  # le panneau repart vers la droite, puis il est caché (gardé)
    from PySide6.QtTest import QTest

    QTest.qWait(400)
    assert not w.settings_showing and w.settings_window is first
    w.open_settings()  # rouvert tout de suite : rien à reconstruire
    QTest.qWait(400)
    assert w.settings_showing and w.settings_window is first
    w.close()


def test_settings_live_in_the_window_and_save_only_when_changed(env, tmp_path):
    """U7 : un panneau dans la fenêtre (plus une fenêtre à part) ; la barre « Enregistrer »
    n'apparaît qu'en cas de modification ; « Annuler » remet tout ; Échap ferme."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from test_desktop import StubAssistant

    from friday.ui.desktop.main_window import MainWindow

    assistant = StubAssistant()
    assistant.components = SimpleNamespace(briefing=None, google=None)
    w = MainWindow(SETTINGS, assistant=assistant, preferences_path=tmp_path / "i.json")
    w.resize(1000, 700)
    w.show()
    w.open_settings()
    QTest.qWait(400)
    panel = w.settings_window
    assert panel.window() is w and panel.isVisible()  # dans la fenêtre de Friday
    assert panel.bar.isHidden()  # rien de changé : pas de barre
    groups = [panel.nav.item(r).text() for r in range(panel.nav.count())
              if panel.nav.item(r).data(Qt.UserRole) is None]  # fmt: skip
    assert groups == ["FRIDAY", "SERVICES", "TRADING", "SYSTÈME"]
    name = panel.forms[0]._controls["FRIDAY_USER_NAME"][0]
    name.setText("Valentin")
    assert not panel.bar.isHidden() and panel.banner.text() == "1 réglage modifié"
    panel.cancel_button.click()
    assert name.text() == "Monsieur" and panel.bar.isHidden()
    name.setText("Valentin")
    panel.save_button.click()
    assert "FRIDAY_USER_NAME=Valentin" in env.read_text("utf-8")
    assert not panel.restart_button.isHidden() and panel.save_button.isHidden()
    w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    QTest.qWait(400)
    assert not w.settings_showing  # refermé (caché, gardé pour la prochaine fois)
    w.close()
