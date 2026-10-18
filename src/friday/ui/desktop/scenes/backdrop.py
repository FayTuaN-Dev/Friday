"""U8 : une scène (météo, carte, globe) devient le fond de toute la fenêtre, comme dans
jarvis-OS. Friday reste par-dessus : la sphère s'efface (son état passe en haut de la
scène), la conversation descend dans le bas de la fenêtre, au-dessus de la barre de saisie.
La souris traverse les zones vides : on fait tourner le globe au-dessus de la conversation.

Transition en fondu par le noir. Constaté : changer la mise en page pendant l'animation
(sphère qui se replie, conversation qui glisse) recalculait tout le chat à chaque image, et
la carte se chargeait pendant que Friday parlait : à-coups et voix hachée. Maintenant : un
voile couvre la fenêtre (0,15 s) ; dessous, tout se met en place d'un coup et la scène se
charge ; le voile s'efface quand elle est prête (0,4 s) ; alors seulement Friday parle
(app/scene_gate.py). La sortie fait pareil.
"""

from PySide6.QtCore import QEasingCurve, QPoint, QTimer, QVariantAnimation
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QSizePolicy

CHAT_SHARE = 0.36  # part de la hauteur laissée à la conversation pendant une scène
COVER_MS = 150  # le voile couvre la fenêtre
REVEAL_MS = 400  # le voile s'efface sur la scène prête
NO_LIMIT = 16_777_215


class BackdropMixin:
    """Méthodes de MainWindow (lit shell, content, veil, scene_spacer, stage, chat…)."""

    scene_mode = False

    def _fade(self, end: float, ms: int, done=None) -> None:
        """Le voile va vers l'opacité `end` (0 : invisible, 255 : couvrant)."""
        old = getattr(self, "_veil_fade", None)
        if old is not None:
            old.stop()
        self.veil.raise_()
        self.title_bar.raise_()
        fade = QVariantAnimation(self, startValue=float(self.veil.alpha), endValue=float(end),
                                 duration=ms, easingCurve=QEasingCurve.InOutQuad)  # fmt: skip
        fade.valueChanged.connect(self.veil.set_alpha)
        if done is not None:
            fade.finished.connect(done)
        self._veil_fade = fade
        fade.start()

    def enter_scene(self, scene, title: str) -> None:
        """Couvrir, poser la scène et la mise en page dessous, attendre, révéler."""
        self.pause_orb(True)  # la sphère ne s'anime plus sous le voile

        def covered() -> None:
            self.scene_layer.show_scene(scene, title)
            if not self.scene_mode:
                self._scene_layout(True)
            self.place_scene()
            if hasattr(scene, "when_shown"):
                scene.when_shown(self._reveal)
            else:
                QTimer.singleShot(60, self._reveal)  # le premier dessin de la météo

        self._fade(255, COVER_MS, covered)

    def _reveal(self) -> None:
        if not self.scene_layer.showing:
            return
        self._after_layout()
        self._fade(0, REVEAL_MS, self._scene_ready)

    def _scene_ready(self) -> None:
        gate = getattr(self.assistant, "scene_gate", None)
        if gate is not None:
            gate.ready()  # Friday peut parler

    def leave_scene(self) -> None:
        """Couvrir, retirer la scène et rendre la sphère dessous, révéler."""

        def covered() -> None:
            self.scene_layer.close_scene(quiet=True)
            self._scene_layout(False)
            self._fade(0, REVEAL_MS)

        self._fade(255, COVER_MS, covered)

    def _scene_layout(self, on: bool) -> None:
        """La mise en page d'un coup, sous le voile."""
        self.scene_mode = on
        self.stage.setVisible(not on)
        self.status.setVisible(not on)
        self.info.setVisible(not on and not self.compact)
        policy = QSizePolicy.Expanding if on else QSizePolicy.Fixed
        self.scene_spacer.changeSize(0, 0, QSizePolicy.Minimum, policy)  # pousse le chat en bas
        if on:
            self._side_panels()  # limites Claude, « En écoute » : cachés, la scène prend tout
            self.scene_layer.show_state(self.status.text(), self.status_color())
            self.chat.setMaximumHeight(int(self.shell.height() * CHAT_SHARE))
        else:
            self.chat.setMaximumHeight(NO_LIMIT)
            self.content.clearMask()
            self.pause_orb(False)
            self._side_panels()
        self.content.layout().activate()

    def place_scene(self) -> None:
        """Le calque couvre toute la fenêtre, sous Friday ; le voile, tout sauf la barre de
        titre ; la conversation garde le bas."""
        self.scene_layer.setGeometry(self.shell.rect())
        self.scene_layer.lower()
        self.glass.lower()  # le fond sous la scène elle-même
        top = self.title_bar.geometry().bottom() + 1
        self.veil.setGeometry(0, top, self.shell.width(), self.shell.height() - top)
        if self.scene_mode:
            self.chat.setMaximumHeight(int(self.shell.height() * CHAT_SHARE))
            QTimer.singleShot(0, self._after_layout)  # une fois la conversation placée

    def _after_layout(self) -> None:
        if not self.scene_mode:
            return
        # Seuls la conversation et la barre de saisie captent la souris : le reste va à la
        # scène (glisser la carte, tourner le globe)
        region = QRegion()
        for widget in (self.chat, self.input):
            region += QRegion(widget.geometry())
        self.content.setMask(region)
        top = self.title_bar.geometry().bottom() + 1
        chat_top = self.chat.mapTo(self.shell, QPoint(0, 0)).y()
        self.scene_layer.set_insets(top, self.shell.height() - chat_top)
