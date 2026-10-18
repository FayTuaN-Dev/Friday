"""Les cartes des colonnes de côté (fenêtre agrandie), au style HUD des limites Claude : titre
espacé à la couleur d'accent, lignes « NOM ··· valeur », barre fine lumineuse et détail en
petit. Une ligne passe à la couleur d'alerte quand sa valeur devient préoccupante."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from friday.ui.desktop import theme
from friday.ui.desktop.theme.stylesheet import FONT_HUD

WIDTH = 250


def style(p) -> str:
    return f"""
    #Hud {{ background: transparent; border: 1px solid {p.accent_glow}; border-radius: 14px; }}
    #Hud QLabel {{ background: transparent; }}
    #HudTitle {{ font-family: "{FONT_HUD}"; font-size: 11px; color: {p.accent};
                 letter-spacing: 4px; }}
    #HudName {{ font-family: "{FONT_HUD}"; font-size: 10px; color: {p.muted};
                letter-spacing: 3px; }}
    #HudValue {{ font-family: "{FONT_HUD}"; font-size: 17px; color: {p.accent}; }}
    #HudValue[alert="true"] {{ color: {p.error}; }}
    #HudDetail {{ font-size: 10px; color: {p.muted}; }}
    #HudBar {{ background: {p.accent_glow}; border: none; border-radius: 2px; }}
    #HudBar::chunk {{ border-radius: 2px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                      stop:0 {p.accent_soft}, stop:1 {p.accent}); }}
    #HudBar[alert="true"]::chunk {{ background: {p.error}; }}
    """  # fmt: skip


def _flag(widget, alert: bool) -> None:
    if widget.property("alert") != alert:
        widget.setProperty("alert", alert)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class Meter:
    """Une ligne de carte : nom et valeur, barre (0 à 100) et détail."""

    def __init__(self, layout: QVBoxLayout, name: str) -> None:
        line = QHBoxLayout()
        self.name = QLabel(name.upper(), objectName="HudName")
        self.value = QLabel(objectName="HudValue", alignment=Qt.AlignRight | Qt.AlignVCenter)
        line.addWidget(self.name, 1, Qt.AlignBottom)
        line.addWidget(self.value)
        self.bar = QProgressBar(objectName="HudBar", maximum=100, textVisible=False)
        self.bar.setFixedHeight(4)
        self.detail = QLabel(objectName="HudDetail")
        layout.addLayout(line)
        layout.addWidget(self.bar)
        layout.addWidget(self.detail)
        layout.addSpacing(5)
        self.widgets = (self.name, self.value, self.bar, self.detail)

    def show(self, value: str, share: float, detail: str = "", alert: bool = False) -> None:
        self.value.setText(value)
        self.bar.setValue(round(max(0.0, min(1.0, share)) * 100))
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))
        _flag(self.value, alert)
        _flag(self.bar, alert)

    def set_visible(self, visible: bool) -> None:
        for widget in self.widgets:
            widget.setVisible(visible)
        if visible and not self.detail.text():
            self.detail.hide()


class HudCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__(objectName="Hud")
        self.setFixedWidth(WIDTH)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 12, 16, 8)
        self.body.setSpacing(3)
        self.body.addWidget(QLabel(title, objectName="HudTitle"))
        self.body.addSpacing(6)
        self.refresh_style()

    def refresh_style(self) -> None:
        self.setStyleSheet(style(theme.current()))  # suit la couleur choisie
