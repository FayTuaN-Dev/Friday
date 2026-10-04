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
    #ToolNotice {{ color: {THINKING}; font-family: "{FONT_HUD}"; font-size: 12px; }}
    #MemoryNotice {{ color: {ACCENT}; font-family: "{FONT_HUD}"; font-size: 12px; }}
    #ConfirmCard {{ background: {PANEL}; border: 1px solid {THINKING}; border-radius: 10px; }}
    #ConfirmCard QLabel {{ background: transparent; }}
    #ConfirmQuestion {{ color: {TEXT}; }}
    #ConfirmCard QPushButton {{
        min-width: 96px; max-width: 120px; border-radius: 15px; font-size: 13px;
        min-height: 30px; max-height: 30px;
    }}
    #ConfirmYes {{ border-color: {LISTENING}; color: {LISTENING}; }}
    #ConfirmYes:hover {{ background: {LISTENING}; color: {BG}; }}
    #ConfirmNo:hover {{ border-color: {ERROR}; color: {ERROR}; }}
    #ClaudeResult {{
        background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px;
    }}
    #ClaudeFiles {{ color: {LISTENING}; font-family: "{FONT_HUD}"; font-size: 12px; }}
    #OpenFolder {{
        min-width: 170px; max-width: 200px; border-radius: 15px; font-size: 13px;
        min-height: 30px; max-height: 30px;
    }}
    #MemoryItem {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}
    #MemoryItem QLabel {{ background: transparent; }}
    #MemoryMeta {{ color: {MUTED}; font-size: 11px; }}
    #Hint {{ color: {MUTED}; font-size: 11px; font-style: italic; }}
    #WeatherNow {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
    #WeatherNow QLabel {{ background: transparent; }}
    #WeatherIcon {{ font-size: 40px; }}
    #WeatherTemp {{ font-family: "{FONT_HUD}"; font-size: 40px; color: {ACCENT}; }}
    #WeatherDetails {{ color: {TEXT}; font-size: 12px; }}
    #WeatherDay {{ font-weight: 600; }}
    #WeatherDayIcon {{ font-size: 18px; }}
    #WeatherRange {{ font-family: "{FONT_HUD}"; color: {ACCENT}; }}
    #WeatherRain {{ color: {MUTED}; font-size: 12px; }}

    /* Pop-ups */
    #Popup {{ background: {BG}; border: 1px solid {ACCENT_DIM}; }}
    #PopupHeader {{ background: {PANEL}; border-bottom: 1px solid {BORDER}; }}
    #PopupTitle {{
        background: transparent; color: {ACCENT}; font-family: "{FONT_HUD}";
        font-size: 12px; letter-spacing: 1px;
    }}
    #PopupClose {{
        min-width: 24px; min-height: 24px; max-width: 24px; max-height: 24px;
        border-radius: 12px; font-size: 11px;
    }}
    #PopupClose:hover {{ border-color: {ERROR}; color: {ERROR}; }}
    #ResultCard {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}
    #ResultCard:hover {{ border-color: {ACCENT_DIM}; }}
    #ResultCard QLabel {{ background: transparent; }}
    #Link {{ font-size: 14px; font-weight: 600; }}
    #Domain {{ color: {LISTENING}; font-size: 11px; }}
    #Snippet {{ color: {MUTED}; font-size: 12px; }}
    #Article {{
        background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px;
        padding: 8px; font-size: 13px;
    }}
    #ImageTile {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; }}
    #ImageTile:hover {{ border-color: {ACCENT}; }}
    """


def link_palette(app) -> None:
    """Couleur des liens cliquables (non réglable par feuille de style)."""
    from PySide6.QtGui import QColor, QPalette

    palette = app.palette()
    palette.setColor(QPalette.Link, QColor(ACCENT))
    palette.setColor(QPalette.LinkVisited, QColor(ACCENT_DIM))
    app.setPalette(palette)
