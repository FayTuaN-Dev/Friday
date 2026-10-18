"""Le style (ST1) : fond à lueur d'accent, cartes de côté en verre sombre."""

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from test_desktop import make_window

from friday.ui.desktop import theme
from friday.ui.desktop.side.hud import style as hud_style
from friday.ui.desktop.theme import PRESETS, build_palette
from friday.ui.desktop.widgets.glass import paint_glass

app = QApplication.instance() or QApplication([])


def test_side_cards_are_dark_glass():
    for preset in PRESETS.values():
        p = build_palette(QColor(preset))
        assert QColor(p.bg).lightnessF() < 0.1  # tout reste sombre
        card = QColor(*map(int, p.card[5:-1].split(", ")))
        assert card.alpha() < 255 and card.lightnessF() < 0.2  # translucide et sombre
        assert p.card in hud_style(p) and p.card_border in hud_style(p)


def test_backdrop_glows_behind_the_sphere_and_darkens_the_edges():
    theme.apply_theme(app, QColor(PRESETS["Cyan"]))
    image = QImage(400, 300, QImage.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    paint_glass(painter, 400, 300, 0)
    painter.end()
    bg = QColor(theme.current().bg)
    centre, corner = image.pixelColor(200, 90), image.pixelColor(2, 298)
    assert centre.blue() > bg.blue() + 10  # la lueur de l'accent derrière la sphère
    assert corner.lightnessF() <= bg.lightnessF()  # la vignette
    theme.apply_theme(app, QColor(PRESETS["Or"]))


def test_backdrop_follows_the_window(tmp_path):
    window = make_window(tmp_path)
    assert not window.glass.isHidden()
    window.resize(900, 700)
    window.glass.repaint()  # le dessin ne plante pas
    assert window.glass.size() == window.shell.size()
