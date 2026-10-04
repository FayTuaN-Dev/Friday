"""Ce que l'écoute mains libres (WakeControl) peut demander à l'assistant."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis.app.assistant import Assistant
    from jarvis.app.wake_control import WakeControl


class HandsFreeTarget:
    def __init__(self, assistant: "Assistant") -> None:
        self.assistant = assistant
        self.wake: WakeControl | None = None  # renseigné par VoiceInputs
        self._said = ""  # dernière phrase dite hors réponse (« Oui ? »), pour l'anti-écho

    @property
    def busy(self) -> bool:
        return self.assistant.busy

    @property
    def awaiting_confirmation(self) -> bool:
        return self.assistant.confirm.waiting

    @property
    def last_reply_text(self) -> str:
        """Ce que Jarvis dit ou vient de dire (pour reconnaître son propre écho)."""
        return f"{self._said} {self.assistant.reply_spoken}".strip()

    def interrupt(self) -> None:
        self.assistant.interrupt()

    def submit_heard(self, text: str) -> None:
        self.assistant.submit_heard(text)

    def acknowledge(self) -> None:
        """« Jarvis » tout seul : il répond, puis écoute la phrase suivante."""
        a = self.assistant
        self._said = f"Oui, {a.settings.user_name} ?"
        # Ouverte tout de suite : on enchaîne souvent la demande pendant qu'il répond « Oui ? ».
        self.wake.open_follow_up()
        a.listener.on_notice("Je vous écoute…")
        if a.voice_on and a.components.speaker:
            a.components.speaker.say(self._said)
            a.components.speaker.wait()  # puis prolongée à partir de la fin de sa réponse
        self.wake.open_follow_up()

    def on_ignored(self, text: str) -> None:
        """Une phrase entendue juste après un échange, mais sans « Jarvis » : on le signale."""
        name = self.assistant.settings.wake_words[0].capitalize()
        self.assistant.listener.on_notice(
            f"Entendu « {text} », sans être sûr que c'était pour moi : commencez par « {name} »."
        )
