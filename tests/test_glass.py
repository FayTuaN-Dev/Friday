"""L'ambiance « verre » (ST1) : palette claire, fond de verre, choix gardé."""

import json

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from test_desktop import make_window

from friday.ui.desktop import theme
from friday.ui.desktop.side.hud import style as hud_style
from friday.ui.desktop.theme import PRESETS, build_palette

app = QApplication.instance() or QApplication([])


def lightness(name: str) -> float:
    return QColor(name).lightnessF()


def test_glass_palette_is_light_with_dark_readable_text():
    for preset in PRESETS.values():
        dark, light = build_palette(QColor(preset)), build_palette(QColor(preset), light=True)
        assert not dark.light and light.light
        assert lightness(light.bg) > 0.85 and lightness(dark.bg) < 0.1
        assert lightness(light.text) < 0.25  # du foncé sur du clair
        assert lightness(light.accent) < 0.5  # l'accent assombri reste lisible
        assert light.card != "transparent" and dark.card == "transparent"
    assert light.card in hud_style(light)  # les cartes de côté givrées


def test_orb_pool_only_in_glass():
    from friday.ui.desktop.widgets.glass import pool

    image = QImage(100, 100, QImage.Format_ARGB32)
    for light, darkened in ((False, False), (True, True)):
        image.fill(QColor("#ffffff"))
        theme.apply_theme(app, QColor(PRESETS["Cyan"]), light=light)
        painter = QPainter(image)
        pool(painter, 50, 50, 30, 50)
        painter.end()
        assert (image.pixelColor(50, 50).lightnessF() < 0.5) == darkened
    theme.apply_theme(app, QColor(PRESETS["Or"]))


def test_ambiance_switches_live_and_is_remembered(tmp_path):
    window = make_window(tmp_path)
    assert window.ambiance == "sombre" and window.glass.isHidden()
    window.set_ambiance("verre")
    assert theme.current().light and not window.glass.isHidden()
    window.resize(900, 700)
    window.glass.repaint()  # le dessin ne plante pas
    assert window.glass.size() == window.shell.size()
    saved = json.loads((tmp_path / "interface.json").read_text("utf-8"))
    assert saved["ambiance"] == "verre"
    again = make_window(tmp_path)
    assert again.ambiance == "verre" and theme.current().light
    again.set_ambiance("sombre")
    assert not theme.current().light and again.glass.isHidden()


def test_appearance_page_offers_the_two_ambiances():
    from friday.ui.desktop.settings.other_pages import AppearancePage

    chosen = []
    page = AppearancePage(QColor("#3cc8ff"), lambda c: None, ambiance="sombre",
                          set_ambiance=chosen.append)  # fmt: skip
    buttons = page.ambiance_buttons
    assert buttons["sombre"].isChecked() and not buttons["verre"].isChecked()
    buttons["verre"].click()
    assert chosen == ["verre"] and buttons["verre"].isChecked()
    assert not buttons["sombre"].isChecked()
