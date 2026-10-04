"""Feuille de style Qt, générée à partir de la palette : formes arrondies, fonds translucides."""

from friday.ui.desktop.theme.palette import Palette

FONT_UI = "Segoe UI"
FONT_HUD = "Segoe UI Light"


def stylesheet(p: Palette) -> str:
    return _window(p) + _chat(p) + _cards(p) + _popups(p)


def _window(p: Palette) -> str:
    return f"""
    QWidget {{ color: {p.text}; font-family: "{FONT_UI}"; font-size: 14px; }}
    QMainWindow, #Transparent {{ background: transparent; }}
    #Shell {{
        background: {p.bg}; border: 1px solid {p.accent_glow}; border-radius: 22px;
    }}
    #TitleBar, #TitleBar QLabel {{ background: transparent; }}
    #Title {{
        font-family: "{FONT_HUD}"; font-size: 15px; color: {p.accent}; letter-spacing: 7px;
    }}
    #Status {{
        background: transparent; font-family: "{FONT_HUD}"; font-size: 13px;
        letter-spacing: 4px;
    }}
    #Info {{ background: transparent; color: {p.muted}; font-size: 11px; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 6px; margin: 4px 0; }}
    QScrollBar::handle:vertical {{
        background: {p.accent_soft}; border-radius: 3px; min-height: 30px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line,
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; height: 0; }}
    QToolTip {{
        background: {p.bg}; color: {p.text}; border: 1px solid {p.accent_soft};
        border-radius: 8px; padding: 4px 8px;
    }}
    QMenu {{
        background: {p.bg}; border: 1px solid {p.accent_soft}; border-radius: 12px;
        padding: 6px;
    }}
    QMenu::item {{ padding: 7px 18px; border-radius: 8px; }}
    QMenu::item:selected {{ background: {p.accent_soft}; }}
    QPushButton {{
        background: transparent; border: none; border-radius: 18px;
        min-width: 36px; min-height: 36px; max-width: 36px; max-height: 36px;
    }}
    QPushButton:hover {{ background: {p.surface_hi}; }}
    QPushButton:pressed, QPushButton:checked {{ background: {p.accent_soft}; }}
    #TitleButton, #CloseButton {{
        min-width: 28px; min-height: 28px; max-width: 28px; max-height: 28px;
        border-radius: 14px;
    }}
    #CloseButton:hover {{ background: rgba(255, 93, 108, 60); }}
    #MicButton:pressed {{ background: {p.accent_soft}; }}
    """


def _chat(p: Palette) -> str:
    return f"""
    #BubbleFriday {{
        background: {p.surface}; border-radius: 18px; border-top-left-radius: 6px;
    }}
    #BubbleUser {{
        background: {p.user_bubble}; border-radius: 18px; border-top-right-radius: 6px;
    }}
    #BubbleAuthor {{
        background: transparent; color: {p.accent}; font-size: 10px; letter-spacing: 2px;
    }}
    #BubbleText {{ background: transparent; }}
    #Notice {{ background: transparent; color: {p.muted}; font-style: italic; font-size: 12px; }}
    #ToolNotice, #MemoryNotice {{ background: transparent; color: {p.accent}; font-size: 12px; }}
    #InputBar {{
        background: {p.surface}; border: 1px solid {p.accent_glow}; border-radius: 25px;
    }}
    QLineEdit {{
        background: transparent; border: none; padding: 8px 4px; font-size: 14px;
        selection-background-color: {p.accent_soft};
    }}
    """


def _cards(p: Palette) -> str:
    return f"""
    #ConfirmCard {{
        background: {p.surface}; border: 1px solid {p.accent_soft}; border-radius: 18px;
    }}
    #ConfirmCard QLabel {{ background: transparent; }}
    #ConfirmCard QPushButton {{
        min-width: 104px; max-width: 130px; min-height: 32px; max-height: 32px;
        border-radius: 16px; font-size: 13px; background: {p.surface_hi};
    }}
    #ConfirmYes {{ color: {p.accent}; }}
    #ConfirmYes:hover {{ background: {p.accent_soft}; }}
    #ConfirmNo:hover {{ background: rgba(255, 93, 108, 60); }}
    #MemoryItem, #ResultCard, #WeatherNow {{
        background: {p.surface}; border-radius: 14px;
    }}
    #ResultCard:hover {{ background: {p.surface_hi}; }}
    #MemoryItem QLabel, #ResultCard QLabel, #WeatherNow QLabel {{ background: transparent; }}
    #MemoryMeta, #Snippet, #WeatherRain {{ color: {p.muted}; font-size: 11px; }}
    #Hint {{ background: transparent; color: {p.muted}; font-size: 11px; font-style: italic; }}
    #Link {{ font-size: 14px; font-weight: 600; }}
    #Domain {{ color: {p.accent}; font-size: 11px; }}
    #WeatherIcon {{ font-size: 40px; }}
    #WeatherTemp {{ font-family: "{FONT_HUD}"; font-size: 42px; color: {p.accent}; }}
    #WeatherDetails {{ font-size: 12px; }}
    #WeatherDay {{ font-weight: 600; }}
    #WeatherDayIcon {{ font-size: 18px; }}
    #WeatherRange {{ color: {p.accent}; }}
    #ClaudeResult, #Article {{
        background: {p.surface}; border: none; border-radius: 14px; padding: 10px;
        font-size: 13px;
    }}
    #ClaudeFiles {{ color: {p.accent}; font-size: 12px; }}
    #OpenFolder {{
        min-width: 180px; max-width: 210px; min-height: 32px; max-height: 32px;
        border-radius: 16px; font-size: 13px; background: {p.surface_hi};
    }}
    #ImageTile {{ background: {p.surface}; border-radius: 12px; }}
    #ImageTile:hover {{ background: {p.surface_hi}; }}
    """


def _popups(p: Palette) -> str:
    return f"""
    #PopupShell {{
        background: {p.bg}; border: 1px solid {p.accent_soft}; border-radius: 20px;
    }}
    #PopupHeader, #PopupTitle {{ background: transparent; }}
    #PopupTitle {{ color: {p.accent}; font-size: 13px; letter-spacing: 1px; }}
    #PopupClose {{
        min-width: 26px; min-height: 26px; max-width: 26px; max-height: 26px;
        border-radius: 13px;
    }}
    #PopupClose:hover {{ background: rgba(255, 93, 108, 60); }}
    """
