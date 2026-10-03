"""Les deux façons de parler à Jarvis : la touche push-to-talk et l'écoute mains libres."""

import logging

from jarvis.app.wake_control import WakeControl, WakeTarget
from jarvis.core.config import Settings

log = logging.getLogger(__name__)


class VoiceInputs:
    def __init__(self, settings: Settings, assistant: WakeTarget) -> None:
        self.settings = settings
        self.assistant = assistant
        self.wake = WakeControl(assistant, settings.wake_words, settings.follow_up_seconds)
        self.ptt = None
        self.hands_free = None

    def start(self, stt) -> None:
        try:
            from jarvis.voice.ptt import PushToTalk

            self.ptt = PushToTalk(
                self.settings.ptt_key, self.assistant.start_listening, self.assistant.stop_listening
            )
        except Exception:
            log.exception("Touche push-to-talk « %s » indisponible", self.settings.ptt_key)

        if self.settings.hands_free:
            try:
                from jarvis.voice.hands_free import HandsFreeListener

                self.hands_free = HandsFreeListener(
                    stt.transcribe,
                    self.wake.on_heard,
                    self.settings.mic_device,
                    self.settings.vad_silence_ms,
                )
                self.hands_free.start()
            except Exception:
                log.exception("Écoute mains libres indisponible")
                self.hands_free = None

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
