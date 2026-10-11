"""Volume par SteelSeries Sonar : constaté, Sonar verrouille le volume général de Windows et
remet à 100 % celui de chaque application ; le réglage passe donc par Sonar lui-même."""

import httpx

from friday.tools.pc.sonar import Sonar, SonarUnavailable, channel_of
from friday.tools.pc.volume import AppAudio, Volume, VolumeTool

SETTINGS = {
    "masters": {"stream": {"monitoring": {"volume": 1.0}, "streaming": {"volume": 1.0}},
                "classic": {"volume": 0.5}},
    "devices": {"media": {"stream": {"monitoring": {"volume": 0.94}}, "classic": {"volume": 0.4}},
                "chatRender": {"stream": {"monitoring": {"volume": 0.76}},
                               "classic": {"volume": 0.3}}},
}  # fmt: skip


def fake_sonar(mode="stream", down=False):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if down:
            return httpx.Response(503)
        if request.url.path == "/mode/":
            return httpx.Response(200, json=mode)
        return httpx.Response(200, json=SETTINGS)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Sonar("http://127.0.0.1:50000", client), calls


def test_sonar_output_names():
    assert (
        channel_of("SteelSeries Sonar - Media (SteelSeries Sonar Virtual Audio Device)") == "media"
    )
    assert channel_of("SteelSeries Sonar - Chat (SteelSeries Sonar Virtual Audio Device)") == (
        "chatRender")  # fmt: skip
    assert channel_of("Speakers (GameDAC Game)") is None


def test_streamer_mode_only_touches_what_the_user_hears():
    sonar, calls = fake_sonar()
    sonar.set(30)
    assert calls[-1] == ("PUT", "/volumeSettings/streamer/monitoring/master/Volume/0.3")
    sonar.mute(True, "media")
    assert calls[-1] == ("PUT", "/volumeSettings/streamer/monitoring/media/Mute/true")
    assert sonar.get() == 100 and sonar.get("media") == 94
    classic, calls = fake_sonar(mode="classic")
    classic.set(15, "chatRender")
    assert calls[-1] == ("PUT", "/volumeSettings/classic/chatRender/Volume/0.15")
    assert classic.get("chatRender") == 30


class Control:
    def __init__(self):
        self.level = 1.0

    def GetMasterVolume(self):
        return self.level

    def SetMasterVolume(self, value, context):
        self.level = value


def volume_with(sonar, apps):
    volume = Volume(find_sonar=lambda: sonar)
    volume.apps = lambda: apps
    volume.locked = lambda: True
    return volume


def test_the_volume_goes_through_sonar_when_it_runs():
    sonar, calls = fake_sonar()
    spotify = AppAudio("Spotify", 1, Control(), "SteelSeries Sonar - Media (SteelSeries …)")
    tool = VolumeTool(volume_with(sonar, [spotify]))
    said = tool.run(level=30).text
    assert "30 %" in said and "dans Sonar" in said
    assert calls[-1] == ("PUT", "/volumeSettings/streamer/monitoring/master/Volume/0.3")
    said = tool.run(level=15, app="spotify").text
    assert "sortie Media de Sonar, où joue Spotify" in said and "autres applications" in said
    assert calls[-1] == ("PUT", "/volumeSettings/streamer/monitoring/media/Volume/0.15")
    assert spotify.control.level == 1.0  # pas le volume Windows de l'application
    assert "Coupé : son général, dans Sonar" in tool.run(mute=True).text


def test_without_sonar_the_windows_mixer_is_used():
    spotify = AppAudio("Spotify", 1, Control(), "Speakers")
    said = VolumeTool(volume_with(None, [spotify])).run(level=40, app="spotify").text
    assert "volume de Spotify" in said and spotify.control.level == 0.4
    down, _ = fake_sonar(down=True)  # Sonar ne répond plus : Windows prend le relais
    said = VolumeTool(volume_with(down, [spotify])).run(level=20).text
    assert "volume de Spotify" in said and spotify.control.level == 0.2


def test_sonar_errors_are_reported():
    down, _ = fake_sonar(down=True)
    try:
        down.set(30)
    except SonarUnavailable as error:
        assert "Sonar ne répond pas" in str(error)
    else:
        raise AssertionError("une erreur était attendue")
