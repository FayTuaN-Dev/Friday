"""Les deux façons de parler à Friday : la touche push-to-talk et l'écoute mains libres."""

import logging
from typing import TYPE_CHECKING

from friday.app.events import AssistantState
from friday.app.hands_free_target import HandsFreeTarget
from friday.app.wake_control import WakeControl
from friday.core.config import Settings
from friday.voice.wake import split_wake_word

if TYPE_CHECKING:
    from friday.app.assistant import Assistant

log = logging.getLogger(__name__)

# Durées du début de phrase retranscrit dans la langue du nom (voir _with_wake_rescue)
HEAD_SECONDS = (1.3,)  # mesuré : 120/120 réveils ; plus long, Whisper repasse au français


class VoiceInputs:
    def __init__(self, settings: Settings, assistant: "Assistant") -> None:
        self.settings = settings
        self.assistant = assistant
        target = HandsFreeTarget(assistant)
        self.wake = WakeControl(target, settings.wake_words, settings.follow_up_seconds)
        target.wake = self.wake
        self.ptt = None
        self.hands_free = None
        self.listening = False  # push-to-talk en cours

    def start(self, stt) -> None:
        try:
            from friday.voice.ptt import PushToTalk

            self.ptt = PushToTalk(
                self.settings.ptt_key, self.assistant.start_listening, self.assistant.stop_listening
            )
        except Exception:
            log.exception("Touche push-to-talk « %s » indisponible", self.settings.ptt_key)

        if self.settings.hands_free:
            try:
                from friday.voice.hands_free import HandsFreeListener

                heard_log = None
                if self.settings.hands_free_record:
                    from friday.core.config import LOGS_DIR
                    from friday.voice.heard_log import HeardLog

                    heard_log = HeardLog(LOGS_DIR / "heard")
                self.hands_free = HandsFreeListener(
                    self._with_wake_rescue(stt),
                    self.wake.on_heard,
                    self.settings.mic_device,
                    self.settings.vad_silence_ms,
                    heard_log,
                )
                self.hands_free.start()
            except Exception:
                log.exception("Écoute mains libres indisponible")
                self.hands_free = None

    def _with_wake_rescue(self, stt):
        """Si le nom manque au début de la phrase, on retranscrit ce début dans la langue du
        nom (« Friday » est anglais). Mesuré sur 120 phrases avec le nom et 36 sans : 120/120
        réveils (contre ~85 % sans ce rattrapage), 1 faux réveil (« Frais du jour »)."""
        language = self.settings.wake_language
        if language == "fr":
            return stt.transcribe
        name = self.settings.wake_words[0].capitalize()

        def transcribe(segment):
            text = stt.transcribe(segment)
            if text and split_wake_word(text, self.wake.pattern) is None:
                for seconds in HEAD_SECONDS:
                    head = stt.transcribe_head(segment, language, seconds)
                    if split_wake_word(head, self.wake.pattern) is not None:
                        log.info("Nom retrouvé en début de phrase (« %s ») : %s", head, text)
                        return f"{name}, {text}"
            return text

        return transcribe

    def press(self) -> None:
        """Touche ou bouton micro enfoncé : on enregistre."""
        a = self.assistant
        if not a.can_listen or self.listening:
            return
        if not a.confirm.waiting:  # on appuie peut-être pour répondre « oui »
            a.interrupt()
        self.listening = True
        self.pause()
        a.components.recorder.start()
        a.set_state(AssistantState.LISTENING)

    def release(self) -> None:
        """Relâché : l'enregistrement part à la transcription."""
        a = self.assistant
        if not self.listening:
            return
        self.listening = False
        a.set_state(AssistantState.THINKING)
        a.submit_audio(a.components.recorder.stop())
        self.resume()

    def pause(self) -> None:
        if self.hands_free:
            self.hands_free.pause()

    def resume(self) -> None:
        if self.hands_free:
            self.hands_free.resume()

    def close(self) -> None:
        if self.ptt:
            self.ptt.close()
        if self.hands_free:
            self.hands_free.stop()

    def describe(self) -> list[str]:
        parts = []
        if self.hands_free:
            parts.append(f"Dites « {self.settings.wake_words[0].capitalize()} »")
        if self.ptt:
            parts.append(f"ou maintenez « {self.settings.ptt_key} »")
        return parts
