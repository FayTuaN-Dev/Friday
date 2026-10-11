"""La scène de la fenêtre principale (J4) : le cœur de Friday (sphère de particules ou
noyau holographique, changé à chaud), l'auto-test du démarrage en surimpression, et les
panneaux latéraux de la fenêtre agrandie (limites Claude, « En écoute »)."""

from PySide6.QtCore import QObject, QPoint, Signal
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
        from PySide6.QtCore import QTimer

        QTimer.singleShot(6000, self.warm_map_when_idle)  # après l'auto-test
        if problem := summary(lines):
            self.chat.add_notice(f"⚠️ {problem}")

    def show_scene_display(self, display) -> bool:
        """Scènes plein écran (J7) : la météo (si activé) et les lieux ; « ferme » / « reviens »
        (Display « close ») les referme aussi. Renvoie True si l'affichage est traité."""
        from friday.tools.popups import CLOSE

        if display.kind == CLOSE:
            self.scene_layer.close_scene()
            return False  # les pop-ups se ferment aussi
        if display.kind == "weather" and not self.settings.scenes:
            return False
        scene = self.scene_layer.scene_for(display.kind, display.data, display.title)
        if scene is None:
            return False
        self.place_scene()
        self.scene_layer.show_scene(scene, display.title)
        self.pause_orb(True)  # la sphère, cachée dessous, ne s'anime plus pour rien
        return True

    def warm_map_when_idle(self) -> None:
        """Prépare la carte 3D quand Friday est au repos (jamais pendant qu'elle parle :
        créer le moteur web bloque la fenêtre un instant et hacherait la voix)."""
        from PySide6.QtCore import QTimer

        from friday.app.events import AssistantState

        if self.scene_layer.map is not None:
            return
        if self.state is AssistantState.IDLE:
            self.scene_layer.warm_map()
        else:
            QTimer.singleShot(3000, self.warm_map_when_idle)

    def scene_follows(self, state) -> None:
        """La carte s'anime quand Friday a fini de parler, et se met en pause quand elle
        écoute ou réfléchit : l'animation prendrait la carte graphique à Whisper et à qwen."""
        from friday.app.events import AssistantState

        if not self.scene_layer.showing_map:
            return
        if state in (AssistantState.LISTENING, AssistantState.THINKING):
            self.scene_layer.map.still()
        elif state is AssistantState.IDLE:
            self.scene_layer.map.animate()

    def pause_orb(self, paused: bool) -> None:
        timer = getattr(self.orb, "_timer", None)
        if timer is not None:
            timer.stop() if paused else timer.start()

    def place_scene(self) -> None:
        """Le calque couvre la fenêtre sous la barre de titre, jusqu'à la barre de saisie."""
        top = self.title_bar.geometry().bottom() + 1
        bottom = self.input.mapTo(self.shell, QPoint(0, 0)).y() - 12
        self.scene_layer.setGeometry(0, top, self.shell.width(), max(100, bottom - top))

    def _side_panels(self, *_args) -> None:
        """Limites Claude et « En écoute » : seulement fenêtre agrandie ou plein écran."""
        wide = self.isMaximized() or self.isFullScreen()
        self.limits.setVisible(wide)
        self.playing.setVisible(wide and self.playing.has_track)
