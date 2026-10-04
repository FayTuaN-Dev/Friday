import os
from types import SimpleNamespace

import pytest

from friday.tools.pc import volume as volume_module
from friday.tools.pc.volume import AppAudio, Volume, VolumeTool


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(volume_module, "PROBE_DELAY", 0)


class Endpoint:
    """Volume général : normal (`locked=False`) ou verrouillé par un mixeur (reste à 100 %)."""

    def __init__(self, locked, level=0.8):
        self.locked, self.level, self.muted = locked, level, 0

    def SetMasterVolumeLevelScalar(self, value, ctx):
        if not self.locked:
            self.level = value

    def GetMasterVolumeLevelScalar(self):
        return 1.0 if self.locked else self.level

    def SetMute(self, muted, ctx):
        self.muted = muted

    def GetMute(self):
        return self.muted


class Control:
    def __init__(self, level=1.0):
        self.level, self.muted = level, 0

    def SetMasterVolume(self, value, ctx):
        self.level = value

    def GetMasterVolume(self):
        return self.level

    def SetMute(self, muted, ctx):
        self.muted = muted


def make_volume(monkeypatch, locked, apps):
    volume = Volume()
    endpoint = Endpoint(locked)
    monkeypatch.setattr(volume, "_endpoint", lambda: endpoint)
    monkeypatch.setattr(volume, "apps", lambda: apps)
    return volume, endpoint


def test_free_volume_uses_the_general_volume_and_is_probed_then_restored(monkeypatch):
    volume, endpoint = make_volume(monkeypatch, locked=False, apps=[])
    assert volume.locked() is False and endpoint.level == 0.8  # valeur remise après le test
    tool = VolumeTool(volume)
    assert "volume général" in tool.run(level=30).text and endpoint.level == 0.3
    assert tool.run().text == "Le volume est à 30 %."
    tool.run(change=-50)
    assert endpoint.level == 0.0


def test_locked_volume_sets_every_application_on_every_output(monkeypatch):
    """Le cas SteelSeries Sonar : Spotify est sur la sortie « Media », Discord sur « Gaming »."""
    spotify, discord = Control(), Control()
    apps = [AppAudio("Spotify", 1, spotify), AppAudio("Discord", 2, discord)]
    volume, _ = make_volume(monkeypatch, locked=True, apps=apps)
    tool = VolumeTool(volume)

    assert "Discord, Spotify" in tool.run(level=15).text
    assert spotify.level == discord.level == 0.15
    tool.run(level=100)  # 15 % puis 100 % : le cas du test réel
    assert spotify.level == discord.level == 1.0
    assert "son de" in tool.run(mute=True).text and spotify.muted


def test_one_application_only(monkeypatch):
    spotify, discord = Control(), Control()
    apps = [AppAudio("Spotify", 1, spotify), AppAudio("Discord", 2, discord)]
    volume, endpoint = make_volume(monkeypatch, locked=False, apps=apps)
    tool = VolumeTool(volume)

    assert "volume de Spotify" in tool.run(level=15, app="spotify").text
    assert spotify.level == 0.15 and discord.level == 1.0 and endpoint.level == 0.8
    assert tool.run(app="Spotify").text == "Le volume est à 15 %."
    assert "ne joue pas de son" in tool.run(level=50, app="Deezer").text


def test_locked_volume_with_nothing_playing_says_so(monkeypatch):
    volume, _ = make_volume(monkeypatch, locked=True, apps=[])
    assert "n'a pas pu" in VolumeTool(volume).run(level=15).text  # plus de faux « c'est fait »


def test_apps_skip_friday_and_system_audio(monkeypatch):
    """Toutes les sorties sont parcourues ; Friday, Sonar et audiodg ne sont jamais touchés."""
    import comtypes
    import psutil
    from pycaw import pycaw

    names = {10: "Spotify.exe", 11: "audiodg.exe", 12: "SteelSeriesSonar.exe", os.getpid(): "py"}

    class Session:
        def __init__(self, pid):
            self.pid = pid

        def QueryInterface(self, iface):
            return self

        def GetProcessId(self):
            return self.pid

    def device(*pids):
        sessions = [Session(p) for p in pids]
        found = SimpleNamespace(GetCount=lambda: len(sessions), GetSession=sessions.__getitem__)
        manager = SimpleNamespace(GetSessionEnumerator=lambda: found)
        return SimpleNamespace(AudioSessionManager=manager)

    devices = [device(11, os.getpid()), device(10, 12)]
    monkeypatch.setattr(comtypes, "CoInitialize", lambda: None)
    monkeypatch.setattr(pycaw.AudioUtilities, "GetAllDevices", staticmethod(lambda *a: devices))
    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(name=lambda: names[pid]))
    assert [a.name for a in Volume().apps()] == ["Spotify"]
