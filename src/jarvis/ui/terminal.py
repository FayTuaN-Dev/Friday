"""Interface terminal (uv run jarvis --cli)."""

import threading

from jarvis.app.assistant import Assistant
from jarvis.app.events import AssistantState, NullListener
from jarvis.core.config import Settings

COMMANDS = "/voix (activer/couper la voix), /reset (nouvelle conversation), /quit"
PROMPT = "Vous  > "


class TerminalUI(NullListener):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.assistant = Assistant(settings, self)
        self.state = AssistantState.LOADING
        self._ready = threading.Event()

    # --- Événements de l'assistant ---

    def on_ready(self, info: str) -> None:
        print(f"Jarvis est prêt, {self.settings.user_name}.\n{info}\nCommandes : {COMMANDS}\n")
        print(PROMPT, end="", flush=True)
        self._ready.set()

    def on_state(self, state: AssistantState) -> None:
        self.state = state
        if state is AssistantState.LISTENING:
            print("\n🎙️  J'écoute… (relâchez la touche pour envoyer)", flush=True)

    def on_user_message(self, text: str, by_voice: bool) -> None:
        if by_voice:
            print(f"Vous 🎙️> {text}")

    def on_reply_start(self) -> None:
        print("Jarvis> ", end="", flush=True)

    def on_reply_chunk(self, text: str) -> None:
        print(text, end="", flush=True)

    def on_reply_end(self, interrupted: bool) -> None:
        print(" [interrompu]" if interrupted else "", end="\n\n")
        print(PROMPT, end="", flush=True)

    def on_notice(self, text: str) -> None:
        print(f"\n({text})\n{PROMPT}", end="", flush=True)

    # --- Boucle clavier ---

    def run(self) -> None:
        print("Chargement de Jarvis…")
        self.assistant.start()
        self._ready.wait()
        while True:
            try:
                text = input().strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                if self.state in (AssistantState.IDLE, AssistantState.LOADING):
                    break
                self.assistant.interrupt()  # Ctrl+C pendant une réponse : on la coupe
                continue
            if text == "/quit":
                break
            if text == "/reset":
                self.assistant.reset()
            elif text == "/voix":
                on = self.assistant.toggle_voice()
                print(f"(Voix {'activée' if on else 'coupée'})\n{PROMPT}", end="", flush=True)
            elif text:
                self.assistant.submit_text(text)
            else:
                print(PROMPT, end="", flush=True)

        self.assistant.shutdown()
        print(f"\nÀ bientôt, {self.settings.user_name}.")


def run(settings: Settings) -> None:
    TerminalUI(settings).run()
