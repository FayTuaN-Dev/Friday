"""Interface terminal : on parle à Jarvis au clavier ou en maintenant la touche push-to-talk."""

import logging
import queue
import threading

from jarvis.brain.llm import Brain, BrainError
from jarvis.core.config import MODELS_DIR, VOICES_DIR, Settings
from jarvis.voice.speaker import Speaker
from jarvis.voice.text import SentenceSplitter

log = logging.getLogger(__name__)

COMMANDS = "/voix (activer/couper la voix), /reset (nouvelle conversation), /quit"


def create_speaker(settings: Settings) -> Speaker | None:
    if not settings.tts_enabled:
        return None
    try:
        from jarvis.voice.tts import PiperTTS

        tts = PiperTTS(settings.tts_voice, VOICES_DIR, settings.tts_speed, settings.tts_speaker)
        return Speaker(tts)
    except Exception:
        log.exception("Voix indisponible, Jarvis continue en mode texte")
        return None


class TerminalApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.brain = Brain(settings)
        self.brain.warmup()
        self.speaker = create_speaker(settings)
        self.voice_on = self.speaker is not None
        # Le clavier et le micro déposent leurs messages ici ; la boucle principale les traite.
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        # Levé quand on appuie sur le push-to-talk : Jarvis s'arrête de parler.
        self.interrupted = threading.Event()
        self.recorder = None
        self.stt = None
        if settings.stt_enabled:
            self._setup_listening()

    def _setup_listening(self) -> None:
        try:
            from jarvis.voice.ptt import PushToTalk
            from jarvis.voice.recorder import Recorder
            from jarvis.voice.stt import WhisperSTT

            self.recorder = Recorder(self.settings.mic_device)
            self.stt = WhisperSTT(self.settings.stt_model, self.settings.stt_device, MODELS_DIR)
            PushToTalk(self.settings.ptt_key, self._start_listening, self._stop_listening)
        except Exception:
            log.exception("Écoute indisponible, Jarvis continue au clavier")
            self.recorder = self.stt = None

    # --- Événements (threads clavier et push-to-talk) ---

    def _start_listening(self) -> None:
        self.interrupted.set()
        if self.speaker:
            self.speaker.stop()
        self.recorder.start()
        print("\n🎙️  J'écoute… (relâchez la touche pour envoyer)", flush=True)

    def _stop_listening(self) -> None:
        self.events.put(("audio", self.recorder.stop()))

    def _read_keyboard(self) -> None:
        while True:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                self.events.put(("quit", None))
                return
            self.events.put(("text", line))

    def _next_event(self) -> tuple[str, object]:
        # Attente par petites tranches pour que Ctrl+C reste réactif sous Windows.
        while True:
            try:
                return self.events.get(timeout=0.2)
            except queue.Empty:
                continue

    # --- Boucle principale ---

    def run(self) -> None:
        threading.Thread(target=self._read_keyboard, daemon=True, name="keyboard").start()
        name = self.settings.user_name
        print(f"Jarvis est prêt, {name}.")
        if self.stt:
            print(f"Maintenez la touche « {self.settings.ptt_key} » pour parler.")
        print(f"Commandes : {COMMANDS}\n")

        while True:
            print("Vous  > ", end="", flush=True)
            try:
                kind, payload = self._next_event()
            except KeyboardInterrupt:
                break
            if kind == "quit":
                break

            if kind == "audio":
                text = self.stt.transcribe(payload)
                if not text:
                    print("(Je n'ai rien entendu)\n")
                    continue
                print(f"Vous 🎙️> {text}")
            else:
                text = str(payload).strip()
                if not text:
                    continue

            if text == "/quit":
                break
            if not self._run_command(text):
                self._respond(text)

        print(f"À bientôt, {name}.")

    def _run_command(self, text: str) -> bool:
        if text == "/reset":
            self.brain.reset()
            print("(Nouvelle conversation)\n")
        elif text == "/voix":
            if self.speaker is None:
                print("(Voix indisponible : voir les logs)\n")
            else:
                self.voice_on = not self.voice_on
                print(f"(Voix {'activée' if self.voice_on else 'coupée'})\n")
        else:
            return False
        return True

    def _respond(self, text: str) -> None:
        self.interrupted.clear()
        speak = self.voice_on and self.speaker is not None
        splitter = SentenceSplitter()
        print("Jarvis> ", end="", flush=True)
        stream = self.brain.reply(text)
        try:
            for chunk in stream:
                if self.interrupted.is_set():
                    stream.close()
                    print(" [interrompu]", end="")
                    break
                print(chunk, end="", flush=True)
                if speak:
                    for sentence in splitter.feed(chunk):
                        self.speaker.say(sentence)
            else:
                if speak:
                    for sentence in splitter.flush():
                        self.speaker.say(sentence)
                    self.speaker.wait()
        except BrainError:
            host = self.settings.ollama_host
            print(f"\n[Impossible de joindre Ollama sur {host}. Est-il lancé ?]")
        except KeyboardInterrupt:
            stream.close()
            if self.speaker:
                self.speaker.stop()
            print(" [interrompu]", end="")
        print("\n")
