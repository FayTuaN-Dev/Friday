"""La scène de la fenêtre principale (J4) : le cœur de Friday (sphère de particules ou
noyau holographique, changé à chaud), l'auto-test du démarrage en surimpression, et les
panneaux latéraux de la fenêtre agrandie (limites Claude, « En écoute »)."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from friday.ui.desktop import preferences
from friday.ui.desktop.widgets.holo import HoloOrb

ORB_STYLES = ("sphere", "holo")  # sphère de particules (J4) ou noyau holographique


def make_orb(style: str) -> QWidget:
    if style == "holo":
        return HoloOrb()
    from friday.ui.desktop.widgets.sphere import ParticleSphere

    return ParticleSphere()


class BootSignal(QObject):
    """L'auto-test du démarrage tourne dans un fil ; ses lignes reviennent par ce signal."""

    done = Signal(list)


class StageMixin:
    """Méthodes de MainWindow pour la scène (lit orb, stage_grid, boot_log, playing…)."""

    def set_orb_style(self, style: str) -> None:
        """Sphère de particules ou noyau holographique, changé à chaud et gardé."""
        if style not in ORB_STYLES or style == self.orb_style:
            return
        old, self.orb_style = self.orb, style
        self.orb = make_orb(style)
        self.orb.set_base_color(self.base)
        self.orb.set_state(self.state)
        if hasattr(self.orb, "progress"):
            self.orb.progress = 1.0  # déjà démarrée : pas de nuage
        self.stage_grid.replaceWidget(old, self.orb)
        old.deleteLater()
        self.boot_log.raise_()
        preferences.save({"orb": style}, self._preferences_path)

    def _boot_check(self) -> None:
        from friday.app.boot_check import boot_lines
        from friday.core.config import DATA_DIR

        try:
            lines = boot_lines(self.assistant.components, self.settings, DATA_DIR)
        except Exception:  # l'auto-test ne doit jamais gêner le démarrage
            lines = []
        self.boot_signal.done.emit(lines)

    def _show_boot(self, lines: list) -> None:
        from friday.app.boot_check import summary

        if lines:
            self.boot_log.start(lines)
        if problem := summary(lines):
            self.chat.add_notice(f"⚠️ {problem}")

    def _side_panels(self, *_args) -> None:
        """Limites Claude et « En écoute » : seulement fenêtre agrandie ou plein écran."""
        wide = self.isMaximized() or self.isFullScreen()
        self.limits.setVisible(wide)
        self.playing.setVisible(wide and self.playing.has_track)
