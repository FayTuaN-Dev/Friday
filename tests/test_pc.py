import json
from types import SimpleNamespace

import pytest

from jarvis.tools.pc import apps_index, windows
from jarvis.tools.pc.apps import CloseAppTool, OpenAppTool
from jarvis.tools.pc.apps_index import App, AppIndex
from jarvis.tools.pc.media import MediaTool, PlayMusicTool
from jarvis.tools.pc.volume import Volume, VolumeTool
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
        return "volume général"

    def mute(self, muted):
        self.muted = muted
        return "son général"


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


class LockedEndpoint:
    """Volume général verrouillé, comme avec SteelSeries Sonar : accepte, mais reste à 100 %."""

    def SetMasterVolumeLevelScalar(self, value, ctx):
        pass

    def GetMasterVolumeLevelScalar(self):
        return 1.0

    def SetMute(self, muted, ctx):
        pass

    def GetMute(self):
        return 0


class Session:
    def __init__(self, name, pid):
        self.Process = SimpleNamespace(pid=pid, name=lambda: name)
        self.level, self.muted = 1.0, 0
        self.SimpleAudioVolume = self

    def SetMasterVolume(self, value, ctx):
        self.level = value

    def GetMasterVolume(self):
        return self.level

    def SetMute(self, muted, ctx):
        self.muted = muted


def test_locked_volume_falls_back_to_each_application(monkeypatch):
    monkeypatch.setattr("jarvis.tools.pc.volume.PROBE_DELAY", 0)
    import os

    spotify, discord, jarvis = Session("Spotify.exe", 1), Session("Discord.exe", 2), None
    jarvis = Session("python.exe", os.getpid())
    volume = Volume()
    monkeypatch.setattr(volume, "_endpoint", LockedEndpoint)
    monkeypatch.setattr(volume, "_audio", lambda: SimpleNamespace(
        GetAllSessions=lambda: [spotify, discord, jarvis]))  # fmt: skip

    result = VolumeTool(volume).run(level=15)
    assert "15 %" in result.text and "Discord, Spotify" in result.text
    assert spotify.level == discord.level == 0.15
    assert jarvis.level == 1.0  # Jarvis reste audible
    assert VolumeTool(volume).run().text == "Le volume est à 15 %."
    VolumeTool(volume).run(level=100)  # le cas du test réel : 15 % puis 100 %
    assert spotify.level == discord.level == 1.0
    assert "chaque application" in VolumeTool(volume).run(mute=True).text and spotify.muted


def test_locked_volume_with_nothing_playing_says_so(monkeypatch):
    monkeypatch.setattr("jarvis.tools.pc.volume.PROBE_DELAY", 0)
    volume = Volume()
    monkeypatch.setattr(volume, "_endpoint", LockedEndpoint)
    monkeypatch.setattr(volume, "_audio", lambda: SimpleNamespace(GetAllSessions=lambda: []))
    assert "n'a pas pu" in VolumeTool(volume).run(level=15).text  # plus de faux « c'est fait »


class FreeEndpoint(LockedEndpoint):
    """Volume général normal : il garde la valeur réglée."""

    level = 0.8

    def SetMasterVolumeLevelScalar(self, value, ctx):
        FreeEndpoint.level = value

    def GetMasterVolumeLevelScalar(self):
        return FreeEndpoint.level


def test_free_volume_is_probed_once_and_restored(monkeypatch):
    monkeypatch.setattr("jarvis.tools.pc.volume.PROBE_DELAY", 0)
    endpoint = FreeEndpoint()
    volume = Volume()
    monkeypatch.setattr(volume, "_endpoint", lambda: endpoint)
    assert volume.locked() is False
    assert FreeEndpoint.level == 0.8  # le test a remis la valeur d'avant
    assert volume.set(100) == "volume général" and FreeEndpoint.level == 1.0
