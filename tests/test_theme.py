from PySide6.QtGui import QColor

from friday.app.events import AssistantState
from friday.ui.desktop.theme import PRESETS, build_palette, parse_color, stylesheet


def test_parse_color_accepts_presets_hex_and_falls_back():
    assert parse_color("cyan").name() == PRESETS["Cyan"]
    assert parse_color(" Or ").name() == PRESETS["Or"]
    assert parse_color("#ff8800").name() == "#ff8800"
    assert parse_color("pas une couleur").name() == PRESETS["Or"]
    assert parse_color(None).name() == PRESETS["Or"]


def test_palette_follows_base_color():
    gold, cyan = build_palette(QColor(PRESETS["Or"])), build_palette(QColor(PRESETS["Cyan"]))
    assert gold.accent != cyan.accent
    assert QColor(gold.bg).lightnessF() < 0.08  # fond toujours sombre
    assert QColor(gold.text).lightnessF() > 0.85  # texte toujours lisible
    assert len(set(gold.states.values())) >= 4  # chaque état a sa nuance
    assert set(gold.states) == set(AssistantState)


def test_white_base_has_no_hue_but_works():
    palette = build_palette(QColor(PRESETS["Blanc"]))
    assert QColor(palette.states[AssistantState.IDLE]).isValid()


def test_stylesheet_uses_palette():
    palette = build_palette(QColor("#a66bff"))
    css = stylesheet(palette)
    assert palette.accent in css and palette.bg in css
    assert "{" in css and "{{" not in css  # accolades bien échappées
