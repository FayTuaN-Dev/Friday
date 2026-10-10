"""Double clap (J3) : deux claquements rapprochés réveillent Friday ; un seul, trois, la
parole, la musique ou un bruit qui dure, non. Sons fabriqués, 16 kHz, blocs de 20 ms."""

import numpy as np

from friday.app.wake_control import WakeControl
from friday.voice.clap import RATE, ClapDetector

BLOCK = RATE // 50
rng = np.random.default_rng(7)


def silence(seconds: float) -> np.ndarray:
    return rng.normal(0, 0.003, int(seconds * RATE)).astype(np.float32)  # pièce calme


def clap(peak: float = 0.7) -> np.ndarray:
    """Un claquement : 15 ms de bruit qui retombe aussitôt."""
    n = int(0.015 * RATE)
    burst = rng.uniform(-1, 1, n) * np.exp(-np.linspace(0, 6, n)) * peak
    return (silence(0.015) + burst).astype(np.float32)


def tone(seconds: float, level: float = 0.5, freq: float = 220) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    return (np.sin(2 * np.pi * freq * t) * level).astype(np.float32)


def run(*parts: np.ndarray, sensitivity: str = "moyenne") -> int:
    fired = []
    detector = ClapDetector(lambda: fired.append(detector.now), sensitivity)
    audio = np.concatenate([silence(1.0), *parts, silence(1.0)])
    for start in range(0, audio.size, BLOCK):
        detector.feed(audio[start : start + BLOCK])
    return len(fired)


def test_a_double_clap_wakes_friday():
    assert run(clap(), silence(0.35), clap()) == 1
    assert run(clap(), silence(0.6), clap()) == 1


def test_one_clap_three_claps_or_badly_spaced_ones_do_not():
    assert run(clap()) == 0
    assert run(clap(), silence(0.35), clap(), silence(0.35), clap()) == 0  # applaudissements
    assert run(clap(), silence(0.05), clap()) == 0  # trop serrés (un seul clap qui résonne)
    assert run(clap(), silence(1.2), clap()) == 0  # trop espacés


def test_speech_music_and_lasting_noise_do_not():
    assert run(tone(0.3), silence(0.3), tone(0.3)) == 0  # deux mots
    assert run(tone(2.0, 0.6)) == 0  # un son qui dure
    music = tone(3.0, 0.15)
    music[int(0.5 * RATE) : int(0.515 * RATE)] += 0.5  # des « coups » dans la musique
    music[int(0.9 * RATE) : int(0.915 * RATE)] += 0.5
    assert run(music) == 0  # pas assez soudains par rapport au fond


def test_cooldown_between_two_wakes():
    assert run(clap(), silence(0.35), clap(), silence(0.6), clap(), silence(0.35), clap()) == 1
    assert run(clap(), silence(0.35), clap(), silence(2.5), clap(), silence(0.35), clap()) == 2


def test_sensitivity():
    soft = (clap(0.2), silence(0.35), clap(0.2))
    assert run(*soft, sensitivity="forte") == 1
    assert run(*soft, sensitivity="faible") == 0
    assert run(*soft, sensitivity="inconnue") == 0  # « moyenne » par défaut


class Target:
    last_reply_text, busy, awaiting_confirmation = "", False, False

    def __init__(self):
        self.calls = []

    def spoke_recently(self, at):
        return False

    def interrupt(self):
        self.calls.append("interrupt")

    def acknowledge(self):
        self.calls.append("acknowledge")

    def submit_heard(self, text):
        self.calls.append(text)

    def on_ignored(self, text):
        pass


def test_the_clap_does_what_friday_alone_does():
    target = Target()
    wake = WakeControl(target, ["friday"], 8.0)
    wake.on_clap()
    assert target.calls == ["interrupt", "acknowledge"]
    target.calls.clear()
    target.awaiting_confirmation = True  # « Je lance ? » : un clap n'est ni oui ni non
    wake.on_clap()
    assert target.calls == []
