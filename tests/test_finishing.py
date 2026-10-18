"""Les finitions du style (ST3) : menus en verre, barre de saisie, trait sous la barre de titre."""

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QFocusEvent
from PySide6.QtWidgets import QApplication, QWidgetAction

from friday.ui.desktop.theme import build_palette
from friday.ui.desktop.widgets.input_bar import InputBar
from friday.ui.desktop.widgets.menus import glass_menu

app = QApplication.instance() or QApplication([])


def test_glass_menu_has_a_title_that_cannot_be_chosen():
    menu = glass_menu(None, "Pages")
    menu.addAction("Trading")
    head, item = menu.actions()
    assert isinstance(head, QWidgetAction) and not head.isEnabled()
    assert head.defaultWidget().text() == "PAGES" and item.text() == "Trading"
    assert menu.objectName() == "GlassMenu" and not glass_menu().actions()


def test_input_bar_lights_up_while_typing():
    bar = InputBar("home")
    assert not bar.property("focused")
    app.sendEvent(bar.edit, QFocusEvent(QEvent.FocusIn))
    assert bar.property("focused") is True
    app.sendEvent(bar.edit, QFocusEvent(QEvent.FocusOut))
    assert bar.property("focused") is False
    assert bar.send.objectName() == "SendButton"


def test_title_bar_line_follows_the_color(tmp_path):
    from test_desktop import make_window

    window = make_window(tmp_path)
    window.apply_color(QColor("#3cc8ff"), save=False)
    line = window.title_bar._line
    assert line.red() == 0x3C and line.alpha() < 255
    window.title_bar.resize(800, 46)
    window.title_bar.repaint()  # le dessin ne plante pas
    assert build_palette(QColor("#3cc8ff")).card_border  # le contour des menus en verre
