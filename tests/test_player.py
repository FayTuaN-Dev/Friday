import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from friday.voice import player as player_module


class FakeStream:
    """Remplace la carte son : c'est le test qui « demande » des blocs audio."""

    latency = 0.2
    device = 0

    def __init__(self, callback, **_kwargs):
        self.callback = callback

    def start(self): ...
    def stop(self): ...
    def close(self): ...

    def pull(self, frames, underflow=False):
        out = np.zeros((frames, 1), dtype=np.float32)
        self.callback(out, frames, None, SimpleNamespace(output_underflow=underflow))
        return out[:, 0]


@pytest.fixture
def player(monkeypatch):
    streams = []

    def open_stream(**kwargs):
        streams.append(FakeStream(**kwargs))
        return streams[-1]

    monkeypatch.setattr(player_module.sd, "OutputStream", open_stream)
    monkeypatch.setattr(player_module.sd, "query_devices", lambda *_: {"name": "test"})
    p = player_module.AudioPlayer(16000)
    p.stream = streams[0]
    return p


def play_in_background(player, audio):
    done = threading.Event()
    threading.Thread(target=lambda: (player.play(audio), done.set()), daemon=True).start()
    time.sleep(0.05)
    return done


def test_silence_when_idle(player):
    assert not player.stream.pull(256).any()


def test_plays_sentences_back_to_back_without_gap(player):
    a, b = np.full(300, 0.1, np.float32), np.full(300, 0.2, np.float32)
    done_a = play_in_background(player, a)
    done_b = play_in_background(player, b)
    out = player.stream.pull(600)
    assert np.allclose(out[:300], 0.1) and np.allclose(out[300:], 0.2)  # enchaînées
    assert done_a.wait(1) and done_b.wait(1)


def test_stop_releases_waiting_play_and_cuts_sound(player):
    done = play_in_background(player, np.full(10_000, 0.5, np.float32))
    player.stream.pull(100)
    player.stop()
    assert done.wait(1)
    assert not player.stream.pull(256).any()  # plus de son


def test_counts_underflows(player):
    player.stream.pull(64, underflow=True)
    assert player.underflows == 1
