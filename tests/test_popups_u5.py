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


def test_a_search_asked_in_words_is_launched_by_the_code():
    from friday.tools.web_search import search_request

    asked = search_request("Friday, trouve-moi des sites pour faire un planning de stream")
    assert asked == ("web_search", {"query": "des sites pour faire un planning de stream"})
    assert search_request("cherche sur internet le prix de la RTX 5070")[1] == {
        "query": "le prix de la rtx 5070"
    }
    for other in ("ouvre le site de twitch", "quelle heure est-il", "les parasites du chat"):
        assert search_request(other) is None


def test_mail_links_open_the_account_linked_to_friday():
    from friday.google.gmail import Gmail

    class Service:
        def users(self):
            return self

        def getProfile(self, userId):
            return self

        def execute(self):
            return {"emailAddress": "moi@exemple.fr"}

    assert Gmail(Service).link("abc") == "https://mail.google.com/mail/u/moi@exemple.fr/#all/abc"
    assert Gmail(lambda: 1 / 0).link("abc").endswith("/u/0/#all/abc")  # adresse inconnue


def test_globe_labels_carry_the_article_link():
    from test_world import world

    from friday.world.globe import globe

    rss = """<rss><channel><item><title>L'Iran menace de fermer le détroit d'Ormuz</title>
    <link>https://lemonde.fr/ormuz</link><pubDate>Sun, 11 Oct 2026 06:00:00 GMT</pubDate>
    </item></channel></rss>"""
    _, data = globe(world(items=(), rss=rss), [])
    assert any(p.get("url") == "https://lemonde.fr/ormuz" for p in data["points"])


def test_scene_page_sends_outside_links_to_the_browser():
    from PySide6.QtCore import QUrl

    from friday.ui.desktop.scenes.links_page import is_outside

    assert is_outside(QUrl("https://lemonde.fr/a"), True)
    assert not is_outside(QUrl("https://friday.local/"), True)
    assert not is_outside(QUrl("https://tiles.example/1.png"), False)  # pas la page elle-même
