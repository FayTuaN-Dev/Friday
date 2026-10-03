"""Thème HUD (style Iron Man). Toutes les couleurs de l'interface sont ici."""

from jarvis.app.events import AssistantState

BG = "#05080d"  # fond de la fenêtre
PANEL = "#0a121b"  # zones (barre de saisie, bulles de Jarvis)
BORDER = "#12384a"
ACCENT = "#00d4ff"  # cyan Jarvis
ACCENT_DIM = "#0a6c87"
TEXT = "#d6f6ff"
MUTED = "#5f8a99"
USER_BUBBLE = "#0d2c3b"
LISTENING = "#3dffb0"  # vert : à l'écoute
THINKING = "#ffb547"  # ambre : réflexion
ERROR = "#ff5d6c"

FONT_UI = "Segoe UI"
FONT_HUD = "Consolas"

STATE_COLORS = {
    AssistantState.LOADING: MUTED,
    AssistantState.IDLE: ACCENT_DIM,
    AssistantState.LISTENING: LISTENING,
    AssistantState.THINKING: THINKING,
    AssistantState.SPEAKING: ACCENT,
}


def stylesheet() -> str:
    return f"""
    QWidget {{
        background: {BG};
        color: {TEXT};
        font-family: "{FONT_UI}";
        font-size: 14px;
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line,
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; height: 0; }}

    #Title {{
        font-family: "{FONT_HUD}"; font-size: 20px; font-weight: bold;
        color: {ACCENT}; letter-spacing: 6px;
    }}
    #Status {{ font-family: "{FONT_HUD}"; font-size: 12px; letter-spacing: 2px; }}
    #Info {{ color: {MUTED}; font-size: 11px; }}

    #BubbleJarvis {{
        background: {PANEL}; border: 1px solid {BORDER};
        border-radius: 12px; border-top-left-radius: 2px;
    }}
    #BubbleUser {{
        background: {USER_BUBBLE}; border: 1px solid {ACCENT_DIM};
        border-radius: 12px; border-top-right-radius: 2px;
    }}
    #BubbleAuthor {{
        background: transparent; color: {ACCENT}; font-family: "{FONT_HUD}";
        font-size: 10px; letter-spacing: 2px;
    }}
    #BubbleText {{ background: transparent; }}
    #Notice {{ color: {MUTED}; font-style: italic; font-size: 12px; }}

    #InputBar {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 22px; }}
    QLineEdit {{
        background: transparent; border: none; padding: 8px 4px;
        selection-background-color: {ACCENT_DIM};
    }}
    QPushButton {{
        background: transparent; border: 1px solid {BORDER}; border-radius: 17px;
        min-width: 34px; min-height: 34px; max-width: 34px; max-height: 34px;
        font-size: 15px; color: {ACCENT};
    }}
    QPushButton:hover {{ border-color: {ACCENT}; }}
    QPushButton:pressed, QPushButton:checked {{ background: {ACCENT_DIM}; color: {TEXT}; }}
    QPushButton:disabled {{ color: {BORDER}; border-color: {BORDER}; }}
    #MicButton:pressed {{ background: {LISTENING}; color: {BG}; }}
    QToolTip {{ background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER}; }}
    """
