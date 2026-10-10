"""Le calque des scènes plein écran (J7) : il recouvre la fenêtre entre la barre de titre et
la barre de saisie (qui reste utilisable), avec un bouton « Retour » et, en sous-titre, ce
que Friday dit. « Reviens », « ferme », Échap ou le bouton ramènent à la sphère."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from friday.ui.desktop import theme
from friday.ui.desktop.theme.stylesheet import FONT_HUD

SUBTITLE_CHARS = 220  # la fin de ce que dit Friday


class SceneLayer(QFrame):
    closed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, objectName="SceneLayer")
        self.scene: QWidget | None = None
        self.map = None  # la carte 3D : créée une fois (warm_map), puis réutilisée
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.setContentsMargins(18, 12, 16, 0)
        self.title = QLabel(objectName="SceneTitle")
        self.back = QPushButton("RETOUR  ✕", objectName="SceneBack", cursor=Qt.PointingHandCursor)
        self.back.clicked.connect(self.close_scene)
        top.addWidget(self.title)
        top.addStretch()
        top.addWidget(self.back)
        self.top = QWidget()
        self.top.setLayout(top)
        self.subtitle = QLabel(objectName="SceneSubtitle", wordWrap=True, alignment=Qt.AlignCenter)
        self.subtitle.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.grid.addWidget(self.top, 0, 0, Qt.AlignTop)
        self.grid.addWidget(self.subtitle, 0, 0, Qt.AlignTop)  # sous le titre
        self._said = ""
        self.refresh_style()
        self.hide()

    def refresh_style(self) -> None:
        p = theme.current()
        self.setStyleSheet(f"""
        #SceneLayer {{ background: {p.bg}; }}
        #SceneTitle {{ font-family: "{FONT_HUD}"; font-size: 12px; letter-spacing: 3px;
                       color: {p.accent}; background: transparent; }}
        #SceneBack {{ font-family: "{FONT_HUD}"; font-size: 11px; letter-spacing: 2px;
                      color: {p.accent}; background: rgba(0, 0, 0, 120);
                      border: 1px solid {p.accent_glow}; border-radius: 14px;
                      padding: 0; min-width: 124px; max-width: 124px;
                      min-height: 32px; max-height: 32px; }}
        #SceneBack:hover {{ background: {p.accent_soft}; }}
        #SceneSubtitle {{ color: white; font-size: 15px; background: rgba(0, 0, 0, 110);
                          border-radius: 12px; padding: 10px 18px; margin: 64px 90px 0 90px; }}
        """)  # fmt: skip

    def scene_for(self, kind: str, data: dict, title: str) -> QWidget | None:
        """Display → scène : « weather » (ciel animé) ou « place » (carte 3D réutilisée)."""
        if kind == "weather":
            from friday.ui.desktop.scenes.weather_scene import WeatherScene

            return WeatherScene(data, title)
        if kind == "place":
            self.warm_map()
            self.map.go(data)
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
        scene.lower()
        # La scène météo écrit elle-même le lieu : pas de second titre par-dessus
        self.title.setText("" if getattr(scene, "draws_title", False) else title.upper())
        self.subtitle.hide()
        self.show()
        self.raise_()

    def close_scene(self, quiet: bool = False) -> None:
        if self.scene is not None:
            self.grid.removeWidget(self.scene)
            if getattr(self.scene, "keep", False):  # la carte : cachée, gardée pour la suite
                self.scene.still()
                self.scene.hide()
            else:
                self.scene.deleteLater()
            self.scene = None
        was_visible = not self.isHidden()
        self.hide()
        if was_visible and not quiet:
            self.closed.emit()

    def start_subtitle(self) -> None:
        self._said = ""

    def add_subtitle(self, chunk: str) -> None:
        """Ce que dit Friday, en bas de la scène (la fin seulement, si c'est long)."""
        if not self.showing:
            return
        self._said += chunk
        text = " ".join(self._said.split())
        self.subtitle.setText(text if len(text) <= SUBTITLE_CHARS
                              else "…" + text[-SUBTITLE_CHARS:].split(" ", 1)[-1])  # fmt: skip
        self.subtitle.setVisible(bool(text))
