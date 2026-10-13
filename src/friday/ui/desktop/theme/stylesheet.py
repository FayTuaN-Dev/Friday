"""Feuille de style Qt, générée à partir de la palette : formes arrondies, fonds translucides."""

from friday.ui.desktop.theme.palette import Palette

FONT_UI = "Segoe UI"
FONT_HUD = "Segoe UI Light"


def stylesheet(p: Palette) -> str:
    return _window(p) + _chat(p) + _cards(p) + _popups(p) + _settings(p)


def _window(p: Palette) -> str:
    return f"""
    QWidget {{ color: {p.text}; font-family: "{FONT_UI}"; font-size: 14px; }}
    QMainWindow, #Transparent {{ background: transparent; }}
    #Shell {{
        background: {p.bg}; border: 1px solid {p.accent_glow}; border-radius: 22px;
    }}
    #Shell[native="true"] {{ border: none; border-radius: 0; }}
    #TitleBar, #TitleBar QLabel {{ background: transparent; }}
    #Title {{
        font-family: "{FONT_HUD}"; font-size: 15px; color: {p.accent}; letter-spacing: 7px;
    }}
    #Title[trading="true"] {{ letter-spacing: 2px; }}
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
    #DaySeparator {{
        background: transparent; color: {p.muted}; font-size: 11px; letter-spacing: 2px;
    }}
    #ToolChip {{
        background: {p.surface}; border: 1px solid {p.accent_glow}; border-radius: 14px;
    }}
    #ToolChip[state="failed"] {{ border-color: {p.error}; }}
    #ToolChip QLabel {{ background: transparent; font-size: 12px; }}
    #ToolChipMark {{ color: {p.accent}; font-size: 13px; }}
    #ToolChip[state="ok"] #ToolChipMark {{ color: #5fd38d; }}
    #ToolChip[state="failed"] #ToolChipMark {{ color: {p.error}; }}
    #ToolChipTime {{ color: {p.muted}; font-size: 11px; }}
    #WelcomeGreeting {{
        background: transparent; font-family: "{FONT_HUD}"; font-size: 26px; color: {p.text};
    }}
    #WelcomeDate {{
        background: transparent; color: {p.accent}; font-size: 11px; letter-spacing: 3px;
    }}
    #WelcomeGlance {{ background: transparent; color: {p.muted}; font-size: 12px; }}
    #Suggestion {{
        min-width: 0; max-width: 16777215; min-height: 38px; max-height: 38px;
        border-radius: 19px; background: {p.surface}; border: 1px solid {p.accent_soft};
        padding: 0 14px; font-size: 13px; text-align: left;
    }}
    #Suggestion:hover {{ background: {p.surface_hi}; border-color: {p.accent}; }}
    #Suggestion:disabled {{ color: {p.muted}; border-color: transparent; }}
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
        min-width: 104px; max-width: 130px; min-height: 34px; max-height: 34px;
        border-radius: 17px; font-size: 13px;
    }}
    #ConfirmYes {{ background: {p.accent}; color: {p.bg}; font-weight: 600; }}
    #ConfirmYes:hover {{ background: {p.text}; }}
    #ConfirmNo {{ background: transparent; border: 1px solid {p.accent_soft}; }}
    #ConfirmNo:hover {{ background: rgba(255, 93, 108, 60); border-color: transparent; }}
    #ConfirmOutcome {{ color: {p.muted}; font-size: 12px; }}
    #ConfirmTime {{ background: {p.surface_hi}; border: none; border-radius: 1px; }}
    #ConfirmTime::chunk {{ background: {p.accent}; border-radius: 1px; }}
    #MemoryItem, #ResultCard, #WeatherNow {{
        background: {p.surface}; border-radius: 14px;
    }}
    #ResultCard:hover, #MemoryItem[link="true"]:hover {{ background: {p.surface_hi}; }}
    #MemoryItem[link="true"]:hover #OpenMark {{ color: {p.accent}; }}
    #OpenMark {{ background: transparent; color: {p.muted}; font-size: 13px; }}
    #MemoryItem QLabel, #ResultCard QLabel, #WeatherNow QLabel {{ background: transparent; }}
    #MemoryMeta, #Snippet, #WeatherRain {{ color: {p.muted}; font-size: 11px; }}
    #Hint {{ background: transparent; color: {p.muted}; font-size: 11px; font-style: italic; }}
    #Link {{ background: transparent; color: {p.accent}; font-size: 14px; font-weight: 600; }}
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


def _settings(p: Palette) -> str:
    return f"""
    #SettingsNav {{
        background: transparent; border: none; outline: none; font-size: 14px;
    }}
    #SettingsNav::item {{ padding: 8px 10px; border-radius: 12px; margin: 1px 0; }}
    #SettingsNav::item:hover {{ background: {p.surface_hi}; }}
    #SettingsNav::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
    #SettingsNav::item:disabled {{
        color: {p.muted}; font-family: "{FONT_HUD}"; font-size: 10px; letter-spacing: 2px;
        padding: 14px 10px 4px 10px; background: transparent;
    }}
    #SettingsCard {{
        background: {p.bg}; border-left: 1px solid {p.accent_glow};
        border-top-left-radius: 18px; border-bottom-left-radius: 18px;
    }}
    #SettingsHeader {{
        font-family: "{FONT_HUD}"; font-size: 13px; letter-spacing: 4px; color: {p.accent};
        background: transparent; padding-left: 4px;
    }}
    #SettingsGroup {{ background: {p.surface}; border-radius: 16px; }}
    #SettingsLine, #SettingsLine QLabel {{ background: transparent; }}
    #SettingsDivider {{ background: rgba(255, 255, 255, 14); margin: 0 16px; }}
    #SettingsSubtitle {{
        background: transparent; color: {p.muted}; font-family: "{FONT_HUD}";
        font-size: 10px; letter-spacing: 2px; padding: 10px 2px 0 2px;
    }}
    #SettingsPage #Hint {{ color: {p.muted}; font-style: normal; font-size: 11px; }}
    #SaveBar {{ background: {p.accent_soft}; border-radius: 16px; }}
    #SaveBarText {{ background: transparent; color: {p.text}; font-size: 13px; }}
    #SettingsPage, #SettingsPage QLabel {{ background: transparent; }}
    #SettingsTitle {{
        font-family: "{FONT_HUD}"; font-size: 20px; color: {p.accent}; padding: 2px 0 6px 0;
    }}
    #SettingsRow {{ background: {p.surface}; border-radius: 14px; }}
    #SettingsLabel {{ font-size: 13px; }}
    #SettingsPage QLineEdit, #SettingsPage QComboBox, #SettingsPage QSpinBox,
    #SettingsPage QDoubleSpinBox {{
        background: {p.bg}; border: 1px solid {p.accent_glow}; border-radius: 10px;
        padding: 5px 10px; font-size: 13px; selection-background-color: {p.accent_soft};
    }}
    #SettingsPage QComboBox QAbstractItemView {{
        background: {p.bg}; border: 1px solid {p.accent_soft};
        selection-background-color: {p.accent_soft};
    }}
    #SettingsSmall, #SettingsPrimary, #SettingsSwatch {{
        min-width: 0; max-width: 600px; min-height: 32px; max-height: 32px; padding: 0 16px;
        border-radius: 16px; font-size: 13px; background: {p.surface_hi};
    }}
    #SettingsPrimary {{ background: {p.accent_soft}; color: {p.text}; font-weight: 600; }}
    #SettingsPrimary:hover, #SettingsSmall:hover, #SettingsSwatch:hover {{
        background: {p.accent_soft};
    }}
    #SettingsSwatch {{ text-align: left; padding-left: 12px; }}
    #SettingsSwatch:checked, #SettingsSmall:checked {{
        background: {p.accent_soft}; border: 1px solid {p.accent};
    }}
    #JournalTable {{
        background: {p.surface}; border: none; border-radius: 12px; gridline-color: {p.bg};
        selection-background-color: {p.accent_soft}; selection-color: {p.text}; font-size: 13px;
    }}
    #JournalTable QHeaderView::section {{
        background: {p.bg}; color: {p.muted}; border: none; padding: 6px 8px;
    }}
    #JournalTable {{ outline: none; }}
    #JournalTable::item {{ padding: 4px 6px; border: none; }}
    #JournalTable::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
    #JournalForm {{ background: {p.surface}; border-radius: 14px; }}
    #JournalForm QLineEdit, #JournalForm QComboBox, #JournalField {{
        background: {p.bg}; border: 1px solid {p.accent_glow}; border-radius: 10px;
        padding: 5px 10px; font-size: 13px; selection-background-color: {p.accent_soft};
    }}
    """
