"""U8 : une scène (météo, carte, globe) devient le fond de toute la fenêtre, comme dans
jarvis-OS. Friday reste par-dessus : la sphère s'efface (son état passe en haut de la
scène), la conversation descend dans le bas de la fenêtre, au-dessus de la barre de saisie.
La souris traverse les zones vides : on fait tourner le globe au-dessus de la conversation.

L'entrée se fait en douceur (constaté : tout changeait d'un coup, pendant que la carte se
chargeait et que Friday parlait) : la sphère se replie et la conversation glisse en bas,
la scène se prépare derrière un voile, puis le voile s'efface quand elle est prête ; alors
seulement Friday parle (app/scene_gate.py). La sortie fait l'inverse.
"""

from PySide6.QtCore import QEasingCurve, QPoint, QTimer, QVariantAnimation
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QSizePolicy

CHAT_SHARE = 0.36  # part de la hauteur laissée à la conversation pendant une scène
MOVE_MS = 400  # la sphère se replie, la conversation glisse
REVEAL_MS = 500  # le voile s'efface
NO_LIMIT = 16_777_215


class BackdropMixin:
    """Méthodes de MainWindow (lit shell, content, scene_spacer, stage, status, info, chat…)."""

    scene_mode = False

    def _animate(self, name: str, start: float, end: float, step, done=None, ms=MOVE_MS):
        """Une animation nommée (relancer la même arrête la précédente)."""
        old = getattr(self, name, None)
        if old is not None:
            old.stop()
        animation = QVariantAnimation(self, startValue=float(start), endValue=float(end),
                                      duration=ms, easingCurve=QEasingCurve.InOutCubic)  # fmt: skip
        animation.valueChanged.connect(step)
        if done is not None:
            animation.finished.connect(done)
        setattr(self, name, animation)
        animation.start()
        return animation

    def set_scene_mode(self, on: bool) -> None:
        if on and self.scene_mode:  # une autre scène à la place de la première
            self._prepare_reveal()
            return
        if on == self.scene_mode:
            return
        self.scene_mode = on
        if on:
            self._enter_scene()
        else:
            self._leave_scene()

    def _enter_scene(self) -> None:
        self.limits.setVisible(False)  # limites Claude, « En écoute » : la scène prend tout
        self.playing.setVisible(False)
        self.info.setVisible(False)
        self.status.setVisible(False)
        self.scene_layer.show_state(self.status.text(), self.status_color())
        self.place_scene()

        def folded() -> None:
            self.stage.setVisible(False)
            self.pause_orb(True)  # la sphère, cachée, ne s'anime plus pour rien

        self._animate("_stage_fold", self.stage.height(), 0,
                      lambda h: self.stage.setFixedHeight(int(h)), folded)  # fmt: skip
        self.scene_spacer.changeSize(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.content.layout().invalidate()
        target = int(self.shell.height() * CHAT_SHARE)
        self._animate("_chat_slide", max(self.chat.height(), target), target,
                      lambda h: self.chat.setMaximumHeight(int(h)))  # fmt: skip
        self._prepare_reveal()

    def _prepare_reveal(self) -> None:
        """Le voile tombe quand la conversation est en place ET la scène prête."""
        waiting = {"moved": False, "ready": False}

        def one_done(what: str) -> None:
            waiting[what] = True
            if all(waiting.values()) and self.scene_mode:
                self._reveal()

        QTimer.singleShot(MOVE_MS, lambda: one_done("moved"))
        scene = self.scene_layer.scene
        if scene is not None and hasattr(scene, "when_shown"):
            scene.when_shown(lambda: one_done("ready"))
        else:
            QTimer.singleShot(60, lambda: one_done("ready"))  # premier dessin de la météo

    def _reveal(self) -> None:
        self._after_layout()
        curtain = self.scene_layer.curtain
        self._animate("_curtain", curtain.alpha, 0, curtain.set_alpha, self._scene_ready,
                      REVEAL_MS)  # fmt: skip

    def _scene_ready(self) -> None:
        gate = getattr(self.assistant, "scene_gate", None)
        if gate is not None:
            gate.ready()  # Friday peut parler

    def _leave_scene(self) -> None:
        self.content.clearMask()
        self.scene_spacer.changeSize(0, 0, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.content.layout().invalidate()
        self.chat.setMaximumHeight(NO_LIMIT)
        self.status.setVisible(True)
        self.info.setVisible(not self.compact)
        self.stage.setFixedHeight(0)
        self.stage.setVisible(True)
        self.pause_orb(False)
        from friday.ui.desktop.stage import STAGE_COMPACT, STAGE_FULL

        self._animate("_stage_fold", 0, STAGE_COMPACT if self.compact else STAGE_FULL,
                      lambda h: self.stage.setFixedHeight(int(h)))  # fmt: skip
        self._side_panels()

    def place_scene(self) -> None:
        """Le calque couvre toute la fenêtre, sous Friday ; la conversation garde le bas."""
        layer = self.scene_layer
        layer.setGeometry(self.shell.rect())
        layer.lower()
        if self.scene_mode and getattr(self, "_chat_slide", None) is not None:
            if self._chat_slide.state() != QVariantAnimation.Running:
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
