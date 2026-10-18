"""Carte « En écoute » (J4), fenêtre agrandie : pochette, titre, artiste, avancement et
boutons précédent / lecture-pause / suivant, au style HUD de Friday (comme les limites
Claude). Lue toutes les 1,5 s dans un fil à part (tools/pc/now_playing.py) ; cachée quand
rien ne joue."""

import atexit
import logging
import threading
import time
import weakref

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from friday.ui.desktop import theme
from friday.ui.desktop.icons import icon
from friday.ui.desktop.theme.stylesheet import FONT_HUD

log = logging.getLogger(__name__)

POLL_SECONDS = 1.5
COVER = 54


def style(p) -> str:
    return f"""
    #Playing {{ background: {p.card}; border: 1px solid {p.card_border or p.accent_glow};
                border-radius: 14px; }}
    #Playing QLabel {{ background: transparent; }}
    #PlayingHead {{ font-family: "{FONT_HUD}"; font-size: 10px; color: {p.accent};
                    letter-spacing: 3px; }}
    #PlayingTitle {{ font-size: 13px; color: {p.text}; }}
    #PlayingArtist {{ font-size: 11px; color: {p.muted}; }}
    #PlayingCover {{ border-radius: 6px; background: {p.accent_glow}; }}
    #PlayingBar {{ background: {p.accent_glow}; border: none; border-radius: 1px; }}
    #PlayingBar::chunk {{ border-radius: 1px; background: {p.accent}; }}
    #PlayingButton {{ background: transparent; border: 1px solid {p.accent_glow};
                      border-radius: 15px; }}
    #PlayingButton:hover {{ background: {p.accent_soft}; }}
    """  # fmt: skip


_POLLERS: "weakref.WeakSet[Poller]" = weakref.WeakSet()


@atexit.register
def _stop_pollers() -> None:
    """Constaté (tests) : un fil qui émet pendant que Qt se ferme fait planter Python à la
    sortie (violation d'accès). Tous s'arrêtent avant."""
    for poller in list(_POLLERS):
        poller.stop()


class Poller(QObject):
    """Lit ce qui joue dans un fil à part et le transmet à l'interface."""

    changed = Signal(object)  # Track ou None

    def __init__(self, backend) -> None:
        super().__init__()
        self.backend = backend
        self._stop = threading.Event()
        _POLLERS.add(self)
        threading.Thread(target=self._loop, daemon=True, name="now-playing").start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            track = self.backend.current()
            if self._stop.is_set():
                return
            try:
                self.changed.emit(track)
            except RuntimeError:  # « Signal source has been deleted » : la carte n'est plus là
                return
            self._stop.wait(POLL_SECONDS)

    def stop(self) -> None:
        self._stop.set()


class NowPlayingCard(QFrame):
    def __init__(self, backend=None) -> None:
        super().__init__(objectName="Playing")
        self.setFixedWidth(250)
        self.track = None
        self._cover_key = None
        self._seen_at = time.monotonic()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        self.head = QLabel("EN ÉCOUTE", objectName="PlayingHead")
        layout.addWidget(self.head)
        line = QHBoxLayout()
        line.setSpacing(10)
        self.cover = QLabel(objectName="PlayingCover")
        self.cover.setFixedSize(COVER, COVER)
        line.addWidget(self.cover)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        self.title = QLabel(objectName="PlayingTitle")
        self.artist = QLabel(objectName="PlayingArtist")
        texts.addStretch()
        texts.addWidget(self.title)
        texts.addWidget(self.artist)
        texts.addStretch()
        line.addLayout(texts, 1)
        layout.addLayout(line)
        self.bar = QProgressBar(objectName="PlayingBar", maximum=1000, textVisible=False)
        self.bar.setFixedHeight(3)
        layout.addWidget(self.bar)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.buttons = {}
        for action in ("previous", "toggle", "next"):
            button = QPushButton(objectName="PlayingButton")
            button.setFixedSize(30, 30)
            button.setIconSize(QSize(14, 14))
            button.clicked.connect(lambda _=False, a=action: self._command(a))
            buttons.addWidget(button)
            self.buttons[action] = button
        buttons.addStretch()
        layout.addLayout(buttons)
        self.backend = backend
        self.poller = None
        if backend is not None:
            self.poller = Poller(backend)
            self.poller.changed.connect(self.show_track)
            self.destroyed.connect(self.poller.stop)  # la carte détruite : le fil s'arrête
        self._clock = QTimer(self, interval=500, timeout=self._advance)  # avance entre 2 lectures
        self._clock.start()
        self.refresh_style()
        self.setVisible(False)

    def refresh_style(self) -> None:
        p = theme.current()
        self.setStyleSheet(style(p))
        playing = self.track is not None and self.track.playing
        for action, name in (("previous", "previous"), ("next", "next"),
                             ("toggle", "pause" if playing else "play")):  # fmt: skip
            self.buttons[action].setIcon(icon(name, p.accent, 16))

    @property
    def has_track(self) -> bool:
        return self.track is not None

    def show_track(self, track) -> None:
        self.track, self._seen_at = track, time.monotonic()
        if track is None:
            return
        self.head.setText(f"EN ÉCOUTE · {track.app.upper()}" if track.app else "EN ÉCOUTE")
        self.title.setText(self._fit(self.title, track.title))
        self.artist.setText(self._fit(self.artist, track.artist))
        self.title.setToolTip(track.title)  # le titre entier au survol
        self.artist.setToolTip(track.artist)
        key = (track.title, track.artist)
        if key != self._cover_key:
            self._cover_key = key
            pixmap = QPixmap()
            if track.cover and pixmap.loadFromData(track.cover):
                pixmap = pixmap.scaled(COVER, COVER, Qt.KeepAspectRatioByExpanding,
                                       Qt.SmoothTransformation)  # fmt: skip
                self.cover.setPixmap(pixmap)
            else:
                self.cover.clear()
        self.refresh_style()
        self._advance()

    def _advance(self) -> None:
        track = self.track
        if track is None or not track.duration:
            self.bar.setValue(0)
            return
        position = track.position + (time.monotonic() - self._seen_at if track.playing else 0)
        share = max(0.0, min(1.0, position / track.duration))  # négative : constaté
        self.bar.setValue(int(1000 * share))

    def _fit(self, label: QLabel, text: str) -> str:
        return label.fontMetrics().elidedText(text, Qt.ElideRight, 156)

    def _command(self, action: str) -> None:
        if self.backend is not None:
            threading.Thread(target=self.backend.command, args=(action,), daemon=True).start()

    def close_poller(self) -> None:
        if self.poller is not None:
            self.poller.stop()


def load_backend():
    """Le lecteur de Windows, ou None ailleurs (ou si l'API n'est pas disponible)."""
    try:
        from friday.tools.pc.now_playing import NowPlaying

        return NowPlaying()
    except Exception as error:  # hors Windows, paquet absent
        log.info("« En écoute » indisponible : %s", error)
        return None
