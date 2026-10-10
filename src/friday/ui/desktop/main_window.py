"""Fenêtre principale, sans bordure et arrondie : barre de titre, noyau holographique,
fil de discussion, barre de saisie. Toute l'interface suit la couleur choisie."""

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from friday.app.assistant import Assistant
from friday.app.events import AssistantState
from friday.core.config import Settings
from friday.ui.desktop import native_window, preferences, theme
from friday.ui.desktop.bridge import QtBridge
from friday.ui.desktop.popups.manager import PopupManager
from friday.ui.desktop.stage import ORB_STYLES, BootSignal, StageMixin, make_orb
from friday.ui.desktop.widgets.chat import ChatView
from friday.ui.desktop.widgets.frame import ResizableFrame
from friday.ui.desktop.widgets.input_bar import InputBar
from friday.ui.desktop.widgets.title_bar import TitleBar

MAX_CONTENT_WIDTH = 820


def dropped_files(mime) -> list[Path]:
    """Fichiers (pas dossiers) glissés depuis l'explorateur."""
    paths = (Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile())
    return [path for path in paths if path.is_file()]


class MainWindow(StageMixin, QMainWindow):
    def __init__(self, settings: Settings, assistant: Assistant | None = None,
                 preferences_path: Path = preferences.PATH) -> None:  # fmt: skip
        super().__init__()
        self.settings = settings  # (page Diagnostic des réglages)
        self.setWindowTitle("F.R.I.D.A.Y.")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        # Coins arrondis : par Windows 11 si possible (fenêtre opaque, ne clignote pas au
        # redimensionnement), sinon par transparence.
        self.native_corners = native_window.native_corners_available()
        if not self.native_corners:
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(540, 860)
        self.setAcceptDrops(True)  # glisser un fichier dans la fenêtre pour le joindre
        self.setMinimumSize(420, 620)
        self._preferences_path = preferences_path
        saved = preferences.load(preferences_path).get("color")
        self.base = theme.parse_color(saved or settings.interface_color)

        self.bridge = QtBridge()
        self.assistant = assistant or Assistant(settings, self.bridge)
        self.state = AssistantState.LOADING

        self.title_bar = TitleBar(self, self.base)
        style = preferences.load(preferences_path).get("orb", "sphere")
        self.orb_style = style if style in ORB_STYLES else "sphere"
        self.orb = make_orb(self.orb_style)
        from friday.ui.desktop.widgets.boot_log import BootLog

        self.boot_log = BootLog()  # séquence de démarrage, en surimpression sur la sphère
        self.boot_signal = BootSignal()
        self.boot_signal.done.connect(self._show_boot)
        self.status = QLabel(objectName="Status", alignment=Qt.AlignCenter)
        self.info = QLabel(objectName="Info", alignment=Qt.AlignCenter, wordWrap=True)
        self.chat = ChatView()
        self.input = InputBar(settings.ptt_key)
        self.input.setEnabled(False)
        self.popups = PopupManager(self)
        from friday.ui.desktop.icons import icon
        from friday.ui.desktop.notifier import Notifier

        # bulles Windows des tâches de fond, quand Friday n'est pas au premier plan
        self.notifier = Notifier(self, icon("pulse", theme.current().accent, 32))
        self.settings_window = None  # fenêtre des réglages (ouverte à la demande)
        self.journal_window = None  # journal de trading (ouvert à la demande)
        self._build_layout()

        self._connect()
        self.apply_color(self.base, save=False)
        self.show_state(AssistantState.LOADING)

    def _build_layout(self) -> None:
        shell = QWidget(objectName="Shell")
        shell.setAttribute(Qt.WA_StyledBackground)
        shell.setProperty("native", self.native_corners)
        # Contenu limité en largeur et centré : reste lisible même en plein écran.
        content = QWidget()
        content.setMaximumWidth(MAX_CONTENT_WIDTH)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 0, 18, 18)
        layout.setSpacing(4)
        self.stage = QWidget()
        self.stage.setFixedHeight(270)
        self.stage_grid = QGridLayout(self.stage)
        self.stage_grid.setContentsMargins(0, 0, 0, 0)
        self.stage_grid.addWidget(self.orb, 0, 0)
        self.stage_grid.addWidget(self.boot_log, 0, 0, Qt.AlignLeft | Qt.AlignBottom)
        layout.addWidget(self.stage)
        layout.addWidget(self.status)
        layout.addWidget(self.info)
        layout.addSpacing(6)
        layout.addWidget(self.chat, 1)
        layout.addSpacing(8)
        layout.addWidget(self.input)
        centered = QHBoxLayout()
        from friday.ui.desktop.widgets.now_playing import NowPlayingCard, load_backend

        self.playing = NowPlayingCard(load_backend())  # « En écoute » : fenêtre agrandie
        if self.playing.poller is not None:
            self.playing.poller.changed.connect(self._side_panels)
        centered.addSpacing(18)
        centered.addWidget(self.playing, 0, Qt.AlignBottom)
        centered.addStretch(1)
        centered.addWidget(content, 100)
        centered.addStretch(1)
        from friday.ui.desktop.widgets.claude_limits import ClaudeLimits

        self.limits = ClaudeLimits()  # session et semaine Claude : seulement fenêtre agrandie
        self.limits.setVisible(False)
        centered.addWidget(self.limits, 0, Qt.AlignTop)
        centered.addSpacing(18)
        from friday.ui.desktop.scenes.layer import SceneLayer

        self.shell = shell
        self.scene_layer = SceneLayer(shell)  # scènes plein écran : météo, carte 3D (J7)
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.title_bar)
        outer.addLayout(centered, 1)
        self.frame = ResizableFrame(shell, opaque=self.native_corners)
        if self.native_corners:
            native_window.round_corners(self)
        self.setCentralWidget(self.frame)

    def _connect(self) -> None:
        b, a = self.bridge, self.assistant
        b.ready.connect(self.on_ready)
        b.state.connect(self.show_state)
        b.user_message.connect(self.chat.add_user)
        b.reply_start.connect(self.chat.start_reply)
        b.reply_start.connect(self.scene_layer.start_subtitle)
        b.reply_chunk.connect(self.chat.append_reply)
        b.reply_chunk.connect(self.scene_layer.add_subtitle)
        b.reply_end.connect(self.chat.end_reply)
        b.notice.connect(self.chat.add_notice)
        b.tool.connect(self.chat.add_tool)
        b.display.connect(self._on_display)
        b.confirmation.connect(
            lambda question: self.chat.add_confirmation(question).answered.connect(
                self.assistant.answer_confirmation
            )
        )
        b.memory.connect(lambda text: self.chat.add_notice(f"🧠 Mémorisé : {text}", "MemoryNotice"))
        b.mic_level.connect(lambda level: self.orb.set_mic_level(level))  # suit le style choisi
        b.speech_audio.connect(lambda audio, rate: self.orb.play_speech(audio, rate))

        self.input.submitted.connect(a.submit_text)
        self.input.mic_pressed.connect(a.start_listening)
        self.input.mic_released.connect(a.stop_listening)
        self.input.voice_toggled.connect(lambda: self.input.set_voice(a.toggle_voice()))
        self.input.reset_clicked.connect(self._reset)
        self.title_bar.color_menu.color_chosen.connect(self.apply_color)
        self.title_bar.settings_button.clicked.connect(self.open_settings)

    def apply_color(self, base: QColor, save: bool = True) -> None:
        """Change la couleur de toute l'interface, à chaud (pop-ups ouverts compris)."""
        self.base = QColor(base)
        palette = theme.apply_theme(QApplication.instance(), self.base)
        self.title_bar.refresh(palette)
        self.input.refresh(palette)
        self.orb.set_base_color(self.base)
        self.playing.refresh_style()
        self.scene_layer.refresh_style()
        if self.native_corners:  # fine bordure Windows, à la couleur de Friday
            native_window.set_border_color(self, QColor(palette.accent).darker(250))
        self.frame.update()
        self.show_state(self.state)
        if save:
            preferences.save({"color": self.base.name()}, self._preferences_path)

    def dragEnterEvent(self, event) -> None:
        if dropped_files(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for path in dropped_files(event.mimeData()):
            self.assistant.attach_file(path)
            self.chat.add_notice(f"📎 {path.name} joint : dites-moi quoi en faire", "ToolNotice")
        event.acceptProposedAction()
        self.input.edit.setFocus()

    def _on_display(self, display) -> None:
        if self.show_scene_display(display):  # météo, lieu : en plein écran
            return
        if display.kind == "settings":  # « ouvre les réglages »
            self.open_settings()
        elif display.kind == "journal":  # « ouvre mon journal »
            self.open_journal()
        elif display.kind == "notification":  # tâche de fond finie : bulle Windows
            self.notifier.notify(display)
        elif display.kind == "trading_mode":  # badge du mode trading
            self.title_bar.set_trading(display.data.get("on", False))
        else:
            self.popups.show(display)

    def open_settings(self) -> None:
        from friday.ui.desktop.settings.window import SettingsWindow

        if self.settings_window is not None and self.settings_window.isVisible():
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return
        self.settings_window = SettingsWindow(self)
        # Fermée, la fenêtre est détruite par Qt : on l'oublie (sinon, plantage à la réouverture).
        self.settings_window.destroyed.connect(self._forget_settings)
        center = self.frameGeometry().center()
        self.settings_window.move(center.x() - self.settings_window.width() // 2,
                                  center.y() - self.settings_window.height() // 2)  # fmt: skip
        self.settings_window.show_animated()

    def _forget_settings(self) -> None:
        self.settings_window = None

    def open_journal(self) -> None:
        """La fenêtre du journal de trading (une seule à la fois)."""
        from friday.ui.desktop.journal.window import JournalWindow

        trading = getattr(self.assistant.components, "trading", None)
        if trading is None:
            self.chat.add_notice("Le mode trading est désactivé (Réglages → Fonctions).")
            return
        if self.journal_window is not None and self.journal_window.isVisible():
            self.journal_window.raise_()
            self.journal_window.activateWindow()
            return
        from friday.core.config import DATA_DIR

        snapshot = getattr(trading, "entry_capture", None)  # capture d'entrée, si possible
        self.journal_window = JournalWindow(trading.journal, snapshot,
                                            DATA_DIR / "journal_captures")  # fmt: skip
        self.journal_window.destroyed.connect(self._forget_journal)
        center = self.frameGeometry().center()
        self.journal_window.move(center.x() - self.journal_window.width() // 2,
                                 center.y() - self.journal_window.height() // 2)  # fmt: skip
        self.journal_window.show_animated()

    def _forget_journal(self) -> None:
        self.journal_window = None

    def restart(self) -> None:
        """Relance Friday (réglages du .env pris en compte) : nouveau processus, puis fermeture."""
        import sys

        from PySide6.QtCore import QProcess

        from friday.core.config import ROOT_DIR

        QProcess.startDetached(sys.executable, ["-m", "friday", *sys.argv[1:]], str(ROOT_DIR))
        self.close()

    def on_ready(self, info: str) -> None:
        self.info.setText(info)
        import threading

        threading.Thread(target=self._boot_check, daemon=True, name="boot-check").start()
        self.input.setEnabled(True)
        self.input.mic.setEnabled(self.assistant.can_listen)
        self.input.set_voice(self.assistant.voice_on)
        self.input.edit.setFocus()

    def show_state(self, state: AssistantState) -> None:
        self.state = state
        self.orb.set_state(state)
        self.status.setText(state.value.upper())
        self.status.setStyleSheet(f"color: {theme.current().states[state]};")

    def _reset(self) -> None:
        self.chat.clear()
        self.assistant.reset()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.place_scene()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape and self.scene_layer.showing:  # Échap : retour
            self.scene_layer.close_scene()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.WindowStateChange:  # plein écran : plus de marge ni de poignée
            self.frame.set_maximized(self.isMaximized())
            self._side_panels()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        self.popups.close_all()
        self.playing.close_poller()
        for window in (self.settings_window, self.journal_window):
            if window is not None:
                window.close()
        self.assistant.shutdown()
        super().closeEvent(event)
