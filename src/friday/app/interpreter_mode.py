"""L'interprète dans Friday : les phrases « traduis la vidéo » / « arrête de traduire »,
reconnues par le code (pas par qwen), et les sous-titres envoyés à l'interface."""

import logging
from typing import TYPE_CHECKING

from friday.app.interpreter import Interpreter, Translator, command
from friday.tools.base import Display

if TYPE_CHECKING:
    from friday.app.assistant import Assistant

log = logging.getLogger(__name__)

STARTED = "Je traduis le son du PC en sous-titres. Dites « arrête de traduire » pour finir."
STOPPED = "Traduction terminée."
NO_EAR = "Je ne peux pas traduire : la transcription de la voix est désactivée."


def build(assistant: "Assistant") -> Interpreter:
    from friday.brain.gpu_gate import GatedClient
    from friday.voice.loopback import Loopback
    from friday.voice.vad import SpeechSegmenter, StreamingVAD

    s, stt = assistant.settings, assistant.components.stt
    return Interpreter(
        stt.transcribe_any,
        Translator(GatedClient(host=s.ollama_host), s.ollama_model, s.ollama_num_ctx),
        lambda french, heard: assistant.listener.on_display(
            Display("subtitle", "Sous-titres", {"text": french, "heard": heard})),
        lambda feed: Loopback(feed, getattr(s, "interpreter_device", "")),
        lambda on_segment: SpeechSegmenter(StreamingVAD(), on_segment, silence_ms=500,
                                           preroll_ms=300, max_ms=8000),
    )  # fmt: skip


class InterpreterMode:
    def __init__(self, assistant: "Assistant", make=build) -> None:
        self.assistant, self._make = assistant, make
        self.interpreter: Interpreter | None = None

    @property
    def on(self) -> bool:
        return bool(self.interpreter and self.interpreter.on)

    def command(self, text: str) -> bool:
        """« Friday, traduis la vidéo » / « arrête de traduire » : True si c'en était une."""
        wanted = command(text)
        if wanted is None or (wanted == "off" and not self.on):
            return False
        if wanted == "on":
            if not self.assistant.components.stt:
                self._say(NO_EAR)
                return True
            if self.interpreter is None:
                self.interpreter = self._make(self.assistant)
            self.interpreter.start()
            self._say(STARTED)
        else:
            self.stop()
            self._say(STOPPED)
        return True

    def stop(self) -> None:
        if self.on:
            self.interpreter.stop()
            self.assistant.listener.on_display(Display("subtitle", "Sous-titres", {"off": True}))

    def _say(self, text: str) -> None:
        """Dite et affichée, sans passer par qwen."""
        a = self.assistant
        a.listener.on_reply_start()
        a.listener.on_reply_chunk(text)
        a.listener.on_reply_end(False)
        speaker = a.components.speaker if a.voice_on else None
        if speaker is not None:
            speaker.say(text)
            speaker.wait()
