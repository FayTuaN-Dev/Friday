"""Sortie audio ouverte en permanence.

Ouvrir un flux audio par phrase (sd.play) crée à chaque fois un instant fragile : si la
carte graphique et le processeur sont très chargés à ce moment-là (début d'une longue
réponse), la sortie grésille. Ici, le flux reste ouvert (il joue du silence au repos), avec
un tampon confortable, et les phrases y sont simplement déposées.
"""

import logging
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

CHECK_EVERY = 0.25  # secondes entre deux vérifications pendant la lecture
STALLED_AFTER = 1.0  # sans demande de la carte son depuis ce délai : flux figé
MAX_EXTRA_WAIT = 3.0  # une phrase ne peut pas attendre plus que sa durée + ce délai


class AudioPlayer:
    def __init__(
        self, sample_rate: int, device: int | str | None = None, latency: float = 0.2
    ) -> None:
        self.sample_rate = sample_rate
        self.underflows = 0  # moments où la carte son a manqué de données
        self.restarts = 0  # flux relancés après s'être figés
        self._queue: deque[tuple[np.ndarray, threading.Event]] = deque()
        self._current: tuple[np.ndarray, threading.Event] | None = None
        self._position = 0
        self._lock = threading.Lock()
        self._device, self._latency = device, latency
        self._last_callback = time.monotonic()
        self._stream = self._open()
        log.info(
            "Sortie audio : %s (tampon %.0f ms)",
            sd.query_devices(self._stream.device)["name"],
            self._stream.latency * 1000,
        )

    def _open(self):
        stream = sd.OutputStream(
            samplerate=self.sample_rate,
            device=self._device,
            channels=1,
            dtype="float32",
            latency=self._latency,
            callback=self._callback,
        )
        stream.start()
        self._last_callback = time.monotonic()
        return stream

    def play(self, audio: np.ndarray, sample_rate: int | None = None) -> None:
        """Joue l'audio et attend qu'il soit passé (ou qu'on l'arrête).

        Surveillé : si la carte son cesse de réclamer du son (flux figé, ça arrive avec les
        mixeurs virtuels comme SteelSeries Sonar), on n'attend pas indéfiniment — Friday
        restait sinon bloquée, sourde à toutes les demandes suivantes."""
        if sample_rate and sample_rate != self.sample_rate:
            raise ValueError(f"Fréquence {sample_rate} Hz ≠ {self.sample_rate} Hz du lecteur")
        before = self.underflows
        done = threading.Event()
        with self._lock:
            self._queue.append((audio.astype(np.float32, copy=False), done))
        deadline = time.monotonic() + audio.size / self.sample_rate + MAX_EXTRA_WAIT
        while not done.wait(CHECK_EVERY):
            if time.monotonic() - self._last_callback > STALLED_AFTER:
                log.warning("Sortie audio figée : redémarrage du flux")
                self._restart()
                break
            if time.monotonic() > deadline:
                log.warning("Phrase toujours en cours après sa durée : abandonnée")
                self.stop()
                break
        if self.underflows > before:
            log.warning("Coupure audio pendant la lecture (%d)", self.underflows - before)

    def _restart(self) -> None:
        self.stop()
        self.restarts += 1
        try:
            self._stream.abort()
            self._stream.close()
        except Exception as error:  # flux déjà mort : on en ouvre un neuf quand même
            log.debug("Fermeture du flux figé : %s", error)
        try:
            self._stream = self._open()
        except Exception:
            log.exception("Impossible de rouvrir la sortie audio")

    def stop(self) -> None:
        """Coupe immédiatement ce qui est en cours et ce qui attend."""
        with self._lock:
            pending = list(self._queue)
            self._queue.clear()
            if self._current:
                pending.append(self._current)
            self._current = None
        for _, done in pending:
            done.set()

    def close(self) -> None:
        self.stop()
        self._stream.stop()
        self._stream.close()

    def _callback(self, out: np.ndarray, frames: int, _time, status) -> None:
        self._last_callback = time.monotonic()
        if status.output_underflow:
            self.underflows += 1
        out.fill(0)  # silence par défaut
        written = 0
        with self._lock:
            while written < frames:
                if self._current is None:
                    if not self._queue:
                        break
                    self._current, self._position = self._queue.popleft(), 0
                audio, done = self._current
                chunk = audio[self._position : self._position + frames - written]
                out[written : written + chunk.size, 0] = chunk
                written += chunk.size
                self._position += chunk.size
                if self._position >= audio.size:
                    done.set()
                    self._current = None
