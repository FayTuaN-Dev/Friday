from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_world import fake_get

from friday.tools.base import Display
from friday.ui.desktop.popups import base
from friday.ui.desktop.popups.items import ItemsPopup, item_row
from friday.world.sources import fetch_headlines

app = QApplication.instance() or QApplication([])


def click(widget) -> None:
    centre = QPointF(widget.rect().center())
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        event = QMouseEvent(kind, centre, centre, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(widget, event)


def test_a_row_with_a_link_opens_it_and_a_plain_row_does_not(monkeypatch):
    opened = []
    monkeypatch.setattr(base.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    linked = item_row({"text": "Facture", "meta": "EDF", "url": "https://mail.google.com/x"})
    plain = item_row({"text": "Acheter du pain"})
    for row in (linked, plain):
        row.resize(300, 50)
        click(row)
    assert opened == ["https://mail.google.com/x"]
    assert linked.property("link") and not plain.property("link")


def test_popup_height_follows_its_content():
    short = ItemsPopup(Display("items", "Notes", {"items": [{"text": "Pain"}]}))
    long = ItemsPopup(
        Display("items", "Notes", {"items": [{"text": f"Note {i}"} for i in range(9)]})
    )
    assert short.height() < 200 < long.height()


def test_popup_slides_into_place():
    popup = ItemsPopup(Display("items", "Notes", {"items": [{"text": "Pain"}]}))
    popup.move(QPoint(200, 200))
    popup.show_animated()
    assert popup.pos().y() > 200  # part un peu plus bas…
    QTest.qWait(450)
    assert popup.pos() == QPoint(200, 200)  # …et arrive à sa place
    popup.close()


def test_headlines_keep_their_article_link():
    rss = """<rss><channel><item><title>Titre</title><link> https://lemonde.fr/a </link>
    <pubDate>Sun, 11 Oct 2026 07:00:00 GMT</pubDate></item></channel></rss>"""
    assert fetch_headlines(fake_get({"lemonde": rss}))[0].link == "https://lemonde.fr/a"
