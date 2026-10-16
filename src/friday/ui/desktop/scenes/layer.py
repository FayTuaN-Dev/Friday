"""Le calque des scènes (J7, U8) : la météo, la carte 3D ou le globe deviennent le FOND de
toute la fenêtre ; Friday (sa conversation, la barre de saisie) reste par-dessus, en bas
(voir backdrop.py). En haut : le titre de la scène, l'état de Friday et « Retour ». Deux
dégradés sombres (haut et bas) gardent le texte lisible sur un ciel clair.
« Reviens », « ferme », Échap ou le bouton ramènent à la sphère."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from friday.ui.desktop import theme
from friday.ui.desktop.theme.stylesheet import FONT_HUD

# Ce que la carte sait montrer : genre d'affichage → méthode de MapScene
SHOWN_ON_MAP = {
    "place": "go",
    "world": "world",
    "route": "route",
    "weather_map": "weather",
    "planes": "planes",
}

TOP_SHADE, BOTTOM_SHADE = 0.22, 0.5  # part de la hauteur assombrie en haut, en bas


class Shade(QWidget):
    """Assombrit le haut (barre de titre) et le bas (conversation) de la scène ; la souris
    passe au travers."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _event) -> None:
        h, bg = self.height(), QColor(theme.current().bg)
        p = QPainter(self)
        for start, end, strong in ((0, h * TOP_SHADE, 0), (h * (1 - BOTTOM_SHADE), h, 1)):
            g = QLinearGradient(0, start, 0, end)
            solid, clear = QColor(bg), QColor(bg)
            solid.setAlpha(150 if strong == 0 else 225)
            clear.setAlpha(0)
            g.setColorAt(0, clear if strong else solid)
            g.setColorAt(1, solid if strong else clear)
            p.fillRect(0, int(start), self.width(), int(end - start) + 1, g)
        p.end()


class Curtain(QWidget):
    """Le voile de la couleur de Friday (backdrop.py) : il couvre la fenêtre le temps de
    changer la mise en page et de préparer la scène, puis s'efface en fondu."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.alpha = 0
        self.hide()

    def set_alpha(self, alpha: float) -> None:
        self.alpha = int(alpha)
        self.setVisible(self.alpha > 0)
        self.update()

    def paintEvent(self, _event) -> None:
        color = QColor(theme.current().bg)
        color.setAlpha(self.alpha)
        p = QPainter(self)
        p.fillRect(self.rect(), color)
        p.end()


class SceneLayer(QFrame):
    closing = Signal()  # « Retour », Échap, « reviens » : la fenêtre fait la transition

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, objectName="SceneLayer")
        self.scene: QWidget | None = None
        self.map = None  # la carte 3D : créée une fois (warm_map), puis réutilisée
        self.insets = (0, 0)  # (haut, bas) : la partie de la scène cachée par Friday
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.shade = Shade(self)
        self.grid.addWidget(self.shade, 0, 0)
        self.top_row = QHBoxLayout()
        self.top_row.setContentsMargins(18, 0, 16, 0)
        self.title = QLabel(objectName="SceneTitle")
        self.state = QLabel(objectName="SceneState")  # « ● PARLE » : la sphère est cachée
        self.back = QPushButton("RETOUR  ✕", objectName="SceneBack", cursor=Qt.PointingHandCursor)
        self.back.clicked.connect(self.close_scene)
        self.top_row.addWidget(self.title)
        self.top_row.addSpacing(12)
        self.top_row.addWidget(self.state)
        self.top_row.addStretch()
        self.top_row.addWidget(self.back)
        self.top = QWidget()
        self.top.setLayout(self.top_row)
        self.grid.addWidget(self.top, 0, 0, Qt.AlignTop)
        self.refresh_style()
        self.hide()

    def refresh_style(self) -> None:
        p = theme.current()
        self.setStyleSheet(f"""
        #SceneLayer {{ background: {p.bg}; }}
        #SceneTitle {{ font-family: "{FONT_HUD}"; font-size: 12px; letter-spacing: 3px;
                       color: {p.accent}; background: transparent; }}
        #SceneState {{ font-family: "{FONT_HUD}"; font-size: 10px; letter-spacing: 2px;
                       background: rgba(0, 0, 0, 110); border-radius: 10px;
                       padding: 3px 10px; }}
        #SceneBack {{ font-family: "{FONT_HUD}"; font-size: 11px; letter-spacing: 2px;
                      color: {p.accent}; background: rgba(0, 0, 0, 120);
                      border: 1px solid {p.accent_glow}; border-radius: 14px;
                      padding: 0; min-width: 124px; max-width: 124px;
                      min-height: 32px; max-height: 32px; }}
        #SceneBack:hover {{ background: {p.accent_soft}; }}
        """)  # fmt: skip

    def show_state(self, text: str, color: str) -> None:
        self.state.setText(f"●  {text.upper()}")
        self.state.setStyleSheet(f"color: {color};")

    def set_insets(self, top: int, bottom: int) -> None:
        """La barre de titre en haut, la conversation en bas : la scène place son sujet
        (texte de la météo, lieu de la carte) entre les deux."""
        self.insets = (top, bottom)
        self.top_row.setContentsMargins(18, top + 6, 16, 0)
        if self.scene is not None and hasattr(self.scene, "set_insets"):
            self.scene.set_insets(top + 50, bottom)  # sous la ligne « titre · Retour »

    def scene_for(self, kind: str, data: dict, title: str) -> QWidget | None:
        """Display → scène : « weather » (ciel animé), ou la carte 3D réutilisée pour un lieu,
        le globe de la veille monde, un itinéraire ou la météo (SHOWN_ON_MAP)."""
        if kind == "weather":
            from friday.ui.desktop.scenes.weather_scene import WeatherScene

            return WeatherScene(data, title)
        if kind in SHOWN_ON_MAP:  # la même carte : lieu, globe, itinéraire, météo
            self.warm_map()
            getattr(self.map, SHOWN_ON_MAP[kind])(data)
            return self.map
        return None

    def warm_map(self) -> None:
        """Prépare la carte (moteur web, bibliothèque, style) une fois, cachée."""
        if self.map is None:
            from friday.ui.desktop.scenes.map_scene import MapScene

            self.map = MapScene(theme.current().accent, self)
            self.map.hide()

    @property
    def showing_map(self) -> bool:
        return self.showing and self.scene is not None and self.scene is self.map

    @property
    def showing(self) -> bool:
        return not self.isHidden() and self.scene is not None  # même fenêtre réduite

    def show_scene(self, scene: QWidget, title: str) -> None:
        self.close_scene(quiet=True)
        self.scene = scene
        self.grid.addWidget(scene, 0, 0)
        scene.show()
        scene.lower()  # sous les dégradés et la ligne du haut
        # La scène météo écrit elle-même le lieu : pas de second titre par-dessus
        # « Tour Eiffel — 75007, France » : le nom suffit (la place est comptée en haut)
        name = title.split(" — ")[0]
        self.title.setText("" if getattr(scene, "draws_title", False) else name.upper())
        self.set_insets(*self.insets)
        self.show()

    def close_scene(self, quiet: bool = False) -> None:
        """`quiet` : tout de suite (sous le voile, ou une autre scène la remplace) ; sinon la
        fenêtre fait la transition (signal `closing`), puis rappelle avec `quiet`."""
        if not quiet:
            if self.showing:
                self.closing.emit()
            return
        if self.scene is not None:
            self.grid.removeWidget(self.scene)
            if getattr(self.scene, "keep", False):  # la carte : cachée, gardée pour la suite
                self.scene.still()
                self.scene.hide()
            else:
                self.scene.deleteLater()
            self.scene = None
        self.hide()
