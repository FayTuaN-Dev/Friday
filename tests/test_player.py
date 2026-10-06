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
    def abort(self): ...
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
    p.streams = streams
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


def test_a_frozen_sound_card_never_blocks_friday(player, monkeypatch):
    """Le flux ne réclame plus rien (mixeur virtuel figé) : la lecture rend la main et le
    flux est rouvert, au lieu de bloquer Friday pour toujours."""
    monkeypatch.setattr(player_module, "STALLED_AFTER", 0.3)
    monkeypatch.setattr(player_module, "CHECK_EVERY", 0.05)
    started = time.monotonic()
    player.play(np.full(16_000, 0.1, np.float32))  # personne ne « tire » le son
    assert time.monotonic() - started < 2
    assert player.restarts == 1 and len(player.streams) == 2  # flux neuf
    done = play_in_background(player, np.full(100, 0.2, np.float32))
    assert np.allclose(player.streams[1].pull(100), 0.2) and done.wait(1)  # et il marche


def test_a_sentence_cannot_wait_forever(player, monkeypatch):
    monkeypatch.setattr(player_module, "MAX_EXTRA_WAIT", 0.2)
    monkeypatch.setattr(player_module, "CHECK_EVERY", 0.05)
    keep_pulling = threading.Event()

    def trickle():  # la carte son réclame, mais un seul échantillon à la fois : trop lent
        while not keep_pulling.is_set():
            player.stream.pull(1)
            time.sleep(0.01)

    threading.Thread(target=trickle, daemon=True).start()
    started = time.monotonic()
    player.play(np.full(1_600, 0.1, np.float32))  # 0,1 s de son
    keep_pulling.set()
    assert time.monotonic() - started < 1.5
