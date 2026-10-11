"""U8 : une scène (météo, carte, globe) devient le fond de toute la fenêtre, comme dans
jarvis-OS. Friday reste par-dessus : la sphère s'efface (son état passe en haut de la
scène), la conversation descend dans le bas de la fenêtre, au-dessus de la barre de saisie.
La souris traverse les zones vides : on fait tourner le globe au-dessus de la conversation.
"""

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QSizePolicy

CHAT_SHARE = 0.36  # part de la hauteur laissée à la conversation pendant une scène


class BackdropMixin:
    """Méthodes de MainWindow (lit shell, content, scene_spacer, stage, status, info, chat…)."""

    scene_mode = False

    def set_scene_mode(self, on: bool) -> None:
        if on == self.scene_mode:
            self.place_scene()
            return
        self.scene_mode = on
        for widget in (self.stage, self.status):
            widget.setVisible(not on)
        self.info.setVisible(not on and not self.compact)
        policy = QSizePolicy.Expanding if on else QSizePolicy.Fixed
        self.scene_spacer.changeSize(0, 0, QSizePolicy.Minimum, policy)  # pousse le chat en bas
        self.content.layout().invalidate()
        self.pause_orb(on)  # la sphère, cachée, ne s'anime plus pour rien
        if on:
            self.scene_layer.show_state(self.status.text(), self.status_color())
        else:
            self.chat.setMaximumHeight(16_777_215)
            self.content.clearMask()
        self.place_scene()

    def place_scene(self) -> None:
        """Le calque couvre toute la fenêtre, sous Friday ; la conversation garde le bas."""
        layer = self.scene_layer
        layer.setGeometry(self.shell.rect())
        layer.lower()
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
