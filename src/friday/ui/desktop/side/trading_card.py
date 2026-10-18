"""La carte « Trading » des colonnes de côté (W3) : le cours des marchés suivis et leur
variation du jour, la prochaine annonce à fort impact (en rouge à moins de 30 min), le
dernier setup du carnet et le résultat de la semaine (journal). Un clic ouvre la page Trading.
Cours et annonces arrivent par un Glance (app/trading_glance.py) ; le reste est lu ici."""

from collections.abc import Callable
from datetime import UTC, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel

from friday.app.trading_glance import Glance
from friday.trading import calendar
from friday.trading.instruments import by_symbol
from friday.trading.journal_stats import week
from friday.trading.market import _digits
from friday.ui.desktop.journal.equity_chart import fr as signed
from friday.ui.desktop.journal.window import GAIN, LOSS
from friday.ui.desktop.side.friday_cards import duration
from friday.ui.desktop.side.hud import HudCard

SOON = 30 * 60  # une annonce à moins de 30 min : en rouge (ne pas entrer juste avant)


def price_text(instrument, price: float) -> str:
    return f"{price:,.{_digits(instrument)}f}".replace(",", " ").replace(".", ",")


def event_text(event: calendar.Event, now: datetime) -> str:
    wait = (event.time - now).total_seconds()
    local = event.time.astimezone(calendar.PARIS)
    when = f"dans {duration(wait)}" if wait < 12 * 3600 else f"{local:%d/%m à %H:%M}"
    return f"{event.title} ({event.currency}) · {when}"


def setup_text(entry: dict, now: datetime) -> str:
    instrument = by_symbol(entry["symbol"])
    name = instrument.name if instrument else entry["symbol"]
    seen = datetime.fromisoformat(entry["seen"])
    ago = duration((now.replace(tzinfo=None) - seen.replace(tzinfo=None)).total_seconds())
    result = "en cours" if entry["result_r"] is None else f"{signed(entry['result_r'], True)} R"
    return f"{name[:1].upper()}{name[1:]} · {entry['side']} · il y a {ago} · {result}"


class TradingCard(HudCard):
    def __init__(self, open_page: Callable[[str], None] | None = None) -> None:
        super().__init__("TRADING")
        self.open_page = open_page
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Ouvrir la page Trading")
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(2)
        self.body.addLayout(self.grid)
        self.rows: list[tuple[QLabel, QLabel, QLabel]] = []
        self.news = self._section("PROCHAINE ANNONCE")
        self.setup = self._section("DERNIER SETUP")
        self.week = self._section("MA SEMAINE")
        self.markets_note = QLabel("Aucun marché suivi : « surveille l'or ».",
                                   objectName="HudDetail", wordWrap=True)  # fmt: skip
        self.body.insertWidget(self.body.indexOf(self.news[0]), self.markets_note)

    def _section(self, title: str) -> tuple[QLabel, QLabel]:
        self.body.addSpacing(4)
        head = QLabel(title, objectName="HudName")
        text = QLabel(objectName="HudDetail", wordWrap=True)
        self.body.addWidget(head)
        self.body.addWidget(text)
        return head, text

    def show_glance(self, glance: Glance, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        while len(self.rows) < len(glance.quotes):
            n = len(self.rows)
            labels = (QLabel(objectName="HudDetail"), QLabel(objectName="HudValue"),
                      QLabel(objectName="HudDetail"))  # fmt: skip
            labels[1].setStyleSheet("font-size: 13px;")
            for column, label in enumerate(labels):
                label.setAlignment((Qt.AlignLeft if column == 0 else Qt.AlignRight)
                                   | Qt.AlignVCenter)  # fmt: skip
                self.grid.addWidget(label, n, column)
            self.rows.append(labels)
        for n, (name, price, change) in enumerate(self.rows):
            shown = n < len(glance.quotes)
            for label in (name, price, change):
                label.setVisible(shown)
            if not shown:
                continue
            instrument, quote = glance.quotes[n]
            name.setText(instrument.name)
            price.setText(price_text(instrument, quote.price) if quote else "—")
            move = quote.change_percent if quote else None
            arrow = "▲" if (move or 0) >= 0 else "▼"
            change.setText("" if move is None else f"{arrow} {signed(move, True)} %")
            change.setStyleSheet(f"color: {(GAIN if (move or 0) >= 0 else LOSS).name()};")
        self.markets_note.setVisible(not glance.quotes)
        head, text = self.news
        text.setText("\n".join(event_text(e, now) for e in glance.events)
                     or "Aucune annonce à fort impact cette semaine pour ces marchés.")  # fmt: skip
        soon = bool(glance.events) and (glance.events[0].time - now).total_seconds() < SOON
        text.setStyleSheet(f"color: {LOSS.name()};" if soon else "")

    def show_local(self, setups, journal, now: datetime | None = None) -> None:
        """Le dernier setup du carnet et la semaine du journal (lus ici : rapides)."""
        now = now or datetime.now()
        entries = setups.all() if setups is not None else []
        last = max(entries, key=lambda e: e["seen"], default=None)
        self.setup[1].setText(setup_text(last, now) if last else "Aucun setup noté.")
        trades = week(journal.all_trades(), now) if journal is not None else []
        total = sum(t.result_r or 0 for t in trades)
        self.week[1].setText(f"{signed(total, True)} R sur {len(trades)} trade(s), 7 jours"
                             if trades else "Aucun trade clôturé ces 7 jours.")  # fmt: skip
        self.week[1].setStyleSheet(f"color: {(GAIN if total >= 0 else LOSS).name()};"
                                   if trades else "")  # fmt: skip

    def mousePressEvent(self, event) -> None:
        """Un clic : la page Trading ; sur le dernier setup, son onglet « Setups »."""
        if self.open_page is not None and event.button() == Qt.LeftButton:
            y = event.position().y()
            on_setup = self.setup[0].y() - 4 <= y < self.week[0].y()
            self.open_page("Setups" if on_setup else "")
        super().mousePressEvent(event)
