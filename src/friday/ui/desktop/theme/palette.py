"""Palette de l'interface, entièrement déduite d'UNE couleur de base (réglable).

Le fond, les panneaux, les bulles, les textes et les couleurs d'état en découlent, pour que
toute l'application reste assortie à l'hologramme quelle que soit la couleur choisie.
"""

from dataclasses import dataclass

from PySide6.QtGui import QColor

from friday.app.events import AssistantState

PRESETS = {
    "Or": "#ffa548",
    "Cyan": "#3cc8ff",
    "Violet": "#a66bff",
    "Vert": "#3dffa0",
    "Rouge": "#ff4848",
    "Blanc": "#dfe8ff",
}
DEFAULT = "Or"

# Variante de la couleur de base selon l'état : (décalage de teinte en degrés,
# facteur de saturation, facteur de luminosité)
STATE_TINTS = {
    AssistantState.LOADING: (0, 0.35, 0.75),
    AssistantState.IDLE: (0, 1.0, 1.0),
    AssistantState.LISTENING: (12, 0.85, 1.15),  # plus clair, plus doux
    AssistantState.THINKING: (-14, 1.15, 1.0),  # plus chaud, plus intense
    AssistantState.SPEAKING: (6, 0.9, 1.12),  # plus lumineux
}
ERROR = QColor("#ff5d6c")


def parse_color(value: str | None) -> QColor:
    """« Or », « cyan », « #ff8800 »… → QColor ; une valeur inconnue donne la couleur par défaut."""
    value = (value or "").strip()
    for name, hex_value in PRESETS.items():
        if value.lower() == name.lower():
            return QColor(hex_value)
    color = QColor(value)
    return color if value and color.isValid() else QColor(PRESETS[DEFAULT])


def hsl(base: QColor, hue_shift: float = 0, saturation: float = 1, lightness: float | None = None,
        light_factor: float = 1) -> QColor:  # fmt: skip
    h, s, light, _ = base.getHslF()
    h = 0.0 if h < 0 else h  # gris / blanc : pas de teinte
    light = lightness if lightness is not None else min(0.92, light * light_factor)
    return QColor.fromHslF((h + hue_shift / 360) % 1.0, min(1.0, s * saturation), light)


def rgba(color: QColor, alpha: float) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {int(alpha * 255)})"


@dataclass(frozen=True)
class Palette:
    base: QColor
    accent: str  # couleur vive (titres, icônes, liens)
    accent_soft: str  # accent translucide (survol, sélection)
    accent_glow: str  # accent très léger (contours)
    bg: str  # fond de la fenêtre
    surface: str  # panneaux (bulles de Friday, barre de saisie, cartes)
    surface_hi: str  # panneau survolé
    user_bubble: str  # bulles de l'utilisateur (teintées de l'accent)
    text: str
    muted: str
    error: str
    states: dict  # AssistantState → nom de couleur

    def state(self, state: AssistantState) -> QColor:
        return QColor(self.states[state])


def state_color(base: QColor, state: AssistantState) -> QColor:
    hue_shift, saturation, light = STATE_TINTS[state]
    return hsl(base, hue_shift, saturation, light_factor=light)


def build_palette(base: QColor) -> Palette:
    return Palette(
        base=base,
        accent=hsl(base, lightness=0.66).name(),
        accent_soft=rgba(base, 0.22),
        accent_glow=rgba(base, 0.14),
        bg=hsl(base, saturation=0.35, lightness=0.045).name(),
        surface=rgba(hsl(base, saturation=0.3, lightness=0.12), 0.72),
        surface_hi=rgba(hsl(base, saturation=0.35, lightness=0.17), 0.85),
        user_bubble=rgba(hsl(base, saturation=0.6, lightness=0.22), 0.78),
        text=hsl(base, saturation=0.2, lightness=0.93).name(),
        muted=hsl(base, saturation=0.15, lightness=0.6).name(),
        error=ERROR.name(),
        states={s: state_color(base, s).name() for s in AssistantState},
    )
