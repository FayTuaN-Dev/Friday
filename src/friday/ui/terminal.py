"""Interface terminal (uv run friday --cli)."""

import threading

from friday.app.assistant import Assistant
from friday.app.events import AssistantState, NullListener
from friday.core.config import Settings

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
        print(f"Friday est prêt, {self.settings.user_name}.\n{info}\nCommandes : {COMMANDS}\n")
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
        print("Friday> ", end="", flush=True)

    def on_reply_chunk(self, text: str) -> None:
        print(text, end="", flush=True)

    def on_reply_end(self, interrupted: bool) -> None:
        print(" [interrompu]" if interrupted else "", end="\n\n")
        print(PROMPT, end="", flush=True)

    def on_tool(self, label: str) -> None:
        print(f"\n  [{label}]", flush=True)

    def on_display(self, display) -> None:
        if display.refresh:  # mise à jour d'une fenêtre : rien à réafficher en terminal
            return
        for r in display.data.get("results", []):
            print(f"  • {r['title']} — {r['url']}")
        if display.kind == "article":
            print(f"  • {display.data.get('url') or display.data.get('path')}")
        for m in display.data.get("memories", []):
            print(f"  [{m['id']}] {m['text']}")
        for d in display.data.get("days", []):
            print(f"  {d['icon']} {d['day']} : {d['min']}–{d['max']} °C, pluie {d['rain']} %")
        if display.kind == "claude":
            print(f"  🤖 {display.data['result'][:800]}")
            for f in display.data.get("files", []):
                print(f"  📄 {f}")
        for item in display.data.get("items", []):
            print(f"  • {item['text']}  ({item.get('meta', '')})")
        if display.kind == "images":
            print(f"  ({len(display.data['images'])} images : visibles dans la fenêtre de bureau)")
        print("Friday> ", end="", flush=True)

    def on_confirmation(self, question: str) -> None:
        print(f"\n  ❓ {question}  (oui / non)\n{PROMPT}", end="", flush=True)

    def on_memory(self, text: str) -> None:
        print(f"\n  🧠 Mémorisé : {text}\n{PROMPT}", end="", flush=True)

    def on_notice(self, text: str) -> None:
        print(f"\n({text})\n{PROMPT}", end="", flush=True)

    # --- Boucle clavier ---

    def run(self) -> None:
        print("Chargement de Friday…")
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
