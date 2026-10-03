"""Chef d'orchestre de Jarvis : écoute → transcription → réflexion → parole.

Ne dépend d'aucune interface : il prévient un `AssistantListener` de ce qui se passe.
Tout le travail lourd tourne dans un thread dédié, l'interface reste fluide.
"""

import logging
import queue
import threading
from collections.abc import Callable

import numpy as np

from jarvis.app.components import Components, describe, load_components
from jarvis.app.events import AssistantListener, AssistantState
from jarvis.app.reply import Reply
from jarvis.app.voice_inputs import VoiceInputs
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
        self.inputs = VoiceInputs(settings, self)
        self._reply: Reply | None = None
        self._said = ""  # dernière phrase dite hors réponse (« Oui ? »), pour l'anti-écho

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

    def submit_heard(self, text: str) -> None:
        """Demande entendue en mains libres (déjà transcrite)."""
        self._events.put(("heard", text))

    def acknowledge(self) -> None:
        """« Jarvis » tout seul : il répond et écoute la phrase suivante."""
        self._said = f"Oui, {self.settings.user_name} ?"
        if self.voice_on and self.components.speaker:
            self.components.speaker.say(self._said)
        self.listener.on_notice("Je vous écoute…")
        self.inputs.wake.open_follow_up()

    @property
    def busy(self) -> bool:
        return self._state in (AssistantState.THINKING, AssistantState.SPEAKING)

    @property
    def last_reply_text(self) -> str:
        """Ce que Jarvis dit ou vient de dire (pour reconnaître son propre écho)."""
        return f"{self._said} {self._reply.spoken if self._reply else ''}".strip()

    def start_listening(self) -> None:
        if not self.can_listen or self._listening:
            return
        self.interrupt()
        self._listening = True
        self.inputs.pause()
        self.components.recorder.start()
        self._set_state(AssistantState.LISTENING)

    def stop_listening(self) -> None:
        if not self._listening:
            return
        self._listening = False
        self._set_state(AssistantState.THINKING)
        self._events.put(("audio", self.components.recorder.stop()))
        self.inputs.resume()

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
        self.inputs.close()
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
        inputs = []
        if self.can_listen:
            self.inputs.start(self.components.stt)
            inputs = self.inputs.describe()
        self.listener.on_ready(describe(self.settings, self.components, inputs))
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
        elif kind == "heard":
            self.listener.on_user_message(str(payload), by_voice=True)
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
        self._said = ""
        self._reply = Reply(self.listener, speaker, self._interrupted)
        self.listener.on_reply_start()
        stream = self.components.brain.reply(text, self._interrupted.is_set)
        try:
            interrupted = self._reply.run(stream)
            if not interrupted:
                self.inputs.wake.open_follow_up()  # relance possible sans redire « Jarvis »
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
