"""File d'attente de parole : synthétise la phrase suivante pendant que la précédente est lue."""

import logging
import queue
import threading
from collections.abc import Callable
from typing import Protocol

import numpy as np

from friday.voice.text import apply_pronunciations, clean_for_speech

log = logging.getLogger(__name__)

PlayFn = Callable[[np.ndarray, int], None]


class TTS(Protocol):
    sample_rate: int

    def synthesize(self, text: str) -> np.ndarray: ...


def _sounddevice_play(audio: np.ndarray, sample_rate: int) -> None:
    import sounddevice as sd

    sd.play(audio, sample_rate, blocking=True)


def _sounddevice_stop() -> None:
    import sounddevice as sd

    sd.stop()


class Speaker:
    """Deux threads : l'un synthétise, l'autre joue. `stop()` coupe la parole immédiatement."""

    def __init__(
        self,
        tts: TTS,
        play: PlayFn = _sounddevice_play,
        stop_playback: Callable[[], None] = _sounddevice_stop,
        on_play: PlayFn | None = None,
        pronunciations: dict[str, str] | None = None,
    ) -> None:
        self.tts = tts
        self.pronunciations = pronunciations or {}  # mots à prononcer autrement (le nom)
        self._play = play
        self._on_play = on_play  # prévenu juste avant chaque phrase jouée (animation)
        self._stop_playback = stop_playback
        self._texts: queue.Queue[tuple[int, str]] = queue.Queue()
        self._audio: queue.Queue[tuple[int, np.ndarray]] = queue.Queue()
        # Chaque stop() change de « génération » : les phrases des anciennes sont ignorées.
        self._generation = 0
        threading.Thread(target=self._synth_loop, daemon=True, name="tts-synth").start()
        threading.Thread(target=self._play_loop, daemon=True, name="tts-play").start()

    def say(self, text: str) -> None:
        text = apply_pronunciations(clean_for_speech(text), self.pronunciations)
        if text:
            self._texts.put((self._generation, text))

    def chime(self) -> None:
        """Petit carillon (avant un rappel), joué dans l'ordre avec les phrases."""
        from friday.voice.sounds import chime

        self._audio.put((self._generation, chime(self.tts.sample_rate)))

    def wait(self) -> None:
        """Bloque jusqu'à la fin de tout ce qui a été demandé."""
        self._texts.join()
        self._audio.join()

    def stop(self) -> None:
        self._generation += 1
        for q in (self._texts, self._audio):
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
                q.task_done()
        self._stop_playback()

    def _synth_loop(self) -> None:
        while True:
            gen, text = self._texts.get()
            try:
                if gen == self._generation:
                    audio = self.tts.synthesize(text)
                    if gen == self._generation and audio.size:
                        self._audio.put((gen, audio))
            except Exception:
                log.exception("Échec de la synthèse de : %r", text)
            finally:
                self._texts.task_done()

    def _play_loop(self) -> None:
        while True:
            gen, audio = self._audio.get()
            try:
                if gen == self._generation:
                    if self._on_play:
                        self._on_play(audio, self.tts.sample_rate)
                    self._play(audio, self.tts.sample_rate)
            except Exception:
                log.exception("Échec de la lecture audio")
            finally:
                self._audio.task_done()
