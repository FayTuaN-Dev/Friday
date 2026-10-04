import json
from types import SimpleNamespace

import pytest

from jarvis.tools.pc import apps_index, windows
from jarvis.tools.pc.apps import CloseAppTool, OpenAppTool
from jarvis.tools.pc.apps_index import App, AppIndex
from jarvis.tools.pc.media import MediaTool, PlayMusicTool, VolumeTool
from jarvis.tools.pc.web import OpenWebsiteTool

APPS = [
    App("Spotify", "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"),
    App("Google Chrome", "Chrome"),
    App("Discord", "com.squirrel.Discord.Discord"),
    App("Calculator", r"{6D809377}\Calc\calc1.exe"),
    App("Notepad", r"{F38BF404}\notepad.exe"),
    App("Paramètres", "windows.immersivecontrolpanel!microsoft.windows.immersivecontrolpanel"),
    App("Visual Studio Code", "Microsoft.VisualStudioCode"),
    App("Steam", "Valve.Steam"),
    App("Steam Support Center", "Valve.SteamSupport"),
]


@pytest.fixture
def index():
    return AppIndex(loader=lambda: APPS)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Spotify", "Spotify"),
        ("spotify", "Spotify"),
        ("chrome", "Google Chrome"),  # équivalence
        ("calculatrice", "Calculator"),  # français → nom anglais du menu Démarrer
        ("bloc-notes", "Notepad"),
        ("parametres", "Paramètres"),  # sans accent
        ("vs code", "Visual Studio Code"),
        ("steam", "Steam"),  # le nom exact gagne sur « Steam Support Center »
        ("discorde", "Discord"),  # faute de frappe
        ("photoshop", None),
    ],
)
def test_find_app(index, query, expected):
    found = index.find(query)
    assert (found.name if found else None) == expected


def test_start_menu_entries_that_are_not_apps_are_skipped(monkeypatch):
    entries = [
        {"Name": "Spotify", "AppID": "Spotify"},
        {"Name": "Release Notes", "AppID": r"C:\VLC\NEWS.txt"},
        {"Name": "Uninstall Steam", "AppID": "Valve.Uninstall"},
    ]
    result = SimpleNamespace(stdout=json.dumps(entries))
    monkeypatch.setattr(apps_index.subprocess, "run", lambda *a, **k: result)
    assert [a.name for a in apps_index.load_start_apps()] == ["Spotify"]


def test_open_app(index):
    launched = []
    tool = OpenAppTool(index, launcher=launched.append)
    assert "Calculator" in tool.run("calculatrice").text
    assert launched == [r"{6D809377}\Calc\calc1.exe"]
    missing = tool.run("photoshoop")
    assert "introuvable" in missing.text and launched == [r"{6D809377}\Calc\calc1.exe"]


def test_close_app_finds_processes_by_several_names(index, monkeypatch):
    asked, closed = [], []

    def find(name):
        asked.append(name)
        return [SimpleNamespace(pid=42)] if name.lower() == "notepad" else []

    monkeypatch.setattr(windows, "find_processes", find)
    monkeypatch.setattr(windows, "close_windows", lambda pids: closed.append(pids) or 1)
    tool = CloseAppTool(index)
    assert tool.needs_confirmation
    assert "fermeture demandée" in tool.run("bloc-notes").text
    assert closed == [{42}] and "notepad" in asked  # nom du .exe tiré de l'AppID

    monkeypatch.setattr(windows, "find_processes", lambda name: [])
    assert "pas ouvert" in tool.run("Discord").text


def test_find_processes_matches_exe_names(monkeypatch):
    procs = [SimpleNamespace(pid=1, info={"name": "Spotify.exe"}),
             SimpleNamespace(pid=2, info={"name": "chrome.exe"}),
             SimpleNamespace(pid=3, info={"name": "svchost.exe"})]  # fmt: skip
    monkeypatch.setattr(windows.psutil, "process_iter", lambda attrs: procs)
    assert [p.pid for p in windows.find_processes("spotify")] == [1]
    assert [p.pid for p in windows.find_processes("Chrome")] == [2]
    assert windows.find_processes("ch") == []  # trop court pour une correspondance partielle


class FakeVolume:
    def __init__(self):
        self.level, self.muted = 50, False

    def get(self):
        return self.level

    def set(self, level):
        self.level = max(0, min(100, level))

    def mute(self, muted):
        self.muted = muted


def test_volume():
    volume = FakeVolume()
    tool = VolumeTool(volume)
    assert "50 %" in tool.run().text
    tool.run(level=30)
    assert volume.level == 30
    tool.run(change=-50)
    assert volume.level == 0
    assert "100 %" in tool.run(change=200).text
    tool.run(mute=True)
    assert volume.muted


def test_media_keys_and_music():
    pressed = []
    MediaTool(press=pressed.append).run("next")
    assert pressed == ["next track"]
    assert "inconnue" in MediaTool(press=pressed.append).run("rewind").text

    opened = []
    PlayMusicTool(True, open_uri=opened.append, open_url=opened.append).run("jazz manouche")
    PlayMusicTool(False, open_uri=opened.append, open_url=opened.append).run("jazz")
    assert opened == ["spotify:search:jazz%20manouche",
                      "https://www.youtube.com/results?search_query=jazz"]  # fmt: skip


def test_open_website():
    opened = []
    tool = OpenWebsiteTool(open_url=opened.append)
    tool.run("youtube.com")
    tool.run("https://mail.google.com")
    assert opened == ["https://youtube.com", "https://mail.google.com"]
    assert "pas une adresse" in tool.run("mon site préféré").text
