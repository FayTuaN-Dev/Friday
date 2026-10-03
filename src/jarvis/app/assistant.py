"""Chef d'orchestre de Jarvis : écoute → transcription → réflexion → parole.

Ne dépend d'aucune interface : il prévient un `AssistantListener` de ce qui se passe.
Tout le travail lourd tourne dans un thread dédié, l'interface reste fluide.
"""

import logging
import queue
import threading
from collections.abc import Callable

import numpy as np

from jarvis.app.components import Components, load_components
from jarvis.app.events import AssistantListener, AssistantState
from jarvis.app.reply import Reply
from jarvis.brain.llm import BrainError
from jarvis.core.config import Settings

log = logging.getLogger(__name__)

Loader = Callable[..., Components]


class Assistant:
    def __init__(
        self, settings: Settings, listener: AssistantListener, loader: Loader = load_components
    ) -> None:
        self.settings = settings
        self.listener = listener
        self._loader = loader
        self.components: Components | None = None
        self.voice_on = settings.tts_enabled
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._interrupted = threading.Event()
        self._listening = False
        self._state: AssistantState | None = None
        self._ptt = None

    # --- API publique (appelable depuis n'importe quel thread) ---

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True, name="assistant").start()

    @property
    def can_listen(self) -> bool:
        c = self.components
        return bool(c and c.recorder and c.stt)

    def submit_text(self, text: str) -> None:
        if text.strip():
            self._events.put(("text", text.strip()))

    def start_listening(self) -> None:
        if not self.can_listen or self._listening:
            return
        self.interrupt()
        self._listening = True
        self.components.recorder.start()
        self._set_state(AssistantState.LISTENING)

    def stop_listening(self) -> None:
        if not self._listening:
            return
        self._listening = False
        self._set_state(AssistantState.THINKING)
        self._events.put(("audio", self.components.recorder.stop()))

    def interrupt(self) -> None:
        """Coupe la parole et la génération en cours."""
        self._interrupted.set()
        if self.components and self.components.speaker:
            self.components.speaker.stop()

    def toggle_voice(self) -> bool:
        if self.components and self.components.speaker:
            self.voice_on = not self.voice_on
            if not self.voice_on:
                self.components.speaker.stop()
        return self.voice_on

    def reset(self) -> None:
        self._events.put(("reset", None))

    def shutdown(self) -> None:
        if self._ptt:
            self._ptt.close()
        self.interrupt()
        self._events.put(("stop", None))

    # --- Thread de travail ---

    def _run(self) -> None:
        self._set_state(AssistantState.LOADING)
        try:
            self.components = self._loader(
                self.settings, self.listener.on_mic_level, self._on_speech_audio
            )
        except Exception:
            log.exception("Chargement de Jarvis impossible")
            self.listener.on_notice("Échec du chargement : voir logs/jarvis.log")
            return
        if self.components.speaker is None:
            self.voice_on = False
        self._setup_push_to_talk()
        self.listener.on_ready(self._describe())
        self._set_state(AssistantState.IDLE)

        while True:
            kind, payload = self._events.get()
            if kind == "stop":
                return
            try:
                self._handle(kind, payload)
            except Exception:
                log.exception("Erreur pendant le traitement de %s", kind)
                self.listener.on_notice("Une erreur est survenue : voir logs/jarvis.log")
            if not self._listening:
                self._set_state(AssistantState.IDLE)

    def _handle(self, kind: str, payload: object) -> None:
        if kind == "reset":
            self.components.brain.reset()
            self.listener.on_notice("Nouvelle conversation")
        elif kind == "text":
            self.listener.on_user_message(str(payload), by_voice=False)
            self._respond(str(payload))
        elif kind == "audio":
            text = self.components.stt.transcribe(payload)
            if not text:
                self.listener.on_notice("Je n'ai rien entendu")
                return
            self.listener.on_user_message(text, by_voice=True)
            self._respond(text)

    def _respond(self, text: str) -> None:
        self._interrupted.clear()
        self._set_state(AssistantState.THINKING)
        speaker = self.components.speaker if self.voice_on else None
        interrupted = False
        self.listener.on_reply_start()
        stream = self.components.brain.reply(text)
        try:
            interrupted = Reply(self.listener, speaker, self._interrupted).run(stream)
        except BrainError:
            host = self.settings.ollama_host
            self.listener.on_notice(f"Impossible de joindre Ollama sur {host}. Est-il lancé ?")
        finally:
            stream.close()
            self.listener.on_reply_end(interrupted)

    # --- Utilitaires ---

    def _on_speech_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        if not self._listening:
            self._set_state(AssistantState.SPEAKING)
        self.listener.on_speech_audio(audio, sample_rate)

    def _set_state(self, state: AssistantState) -> None:
        if state != self._state:
            self._state = state
            self.listener.on_state(state)

    def _setup_push_to_talk(self) -> None:
        if not self.can_listen:
            return
        try:
            from jarvis.voice.ptt import PushToTalk

            self._ptt = PushToTalk(self.settings.ptt_key, self.start_listening, self.stop_listening)
        except Exception:
            log.exception("Touche push-to-talk « %s » indisponible", self.settings.ptt_key)

    def _describe(self) -> str:
        c = self.components
        parts = [f"Cerveau : {self.settings.ollama_model}"]
        parts.append(f"Voix : {self.settings.tts_voice}" if c.speaker else "Voix : désactivée")
        if self.can_listen:
            parts.append(f"Parler : maintenir « {self.settings.ptt_key} »")
        else:
            parts.append("Écoute : désactivée")
        return " · ".join(parts)
