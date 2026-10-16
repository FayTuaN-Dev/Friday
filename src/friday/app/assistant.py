"""Chef d'orchestre de Friday : écoute → transcription → réflexion → parole.

Ne dépend d'aucune interface : il prévient un `AssistantListener` de ce qui se passe.
Tout le travail lourd tourne dans un thread dédié, l'interface reste fluide.
"""

import logging
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from friday.app.attachments import Attachments
from friday.app.briefing_trigger import morning_request
from friday.app.components import Components, describe, load_components
from friday.app.confirmations import ConfirmationGate
from friday.app.events import AssistantListener, AssistantState
from friday.app.game_mode import GameMode
from friday.app.reply import Reply
from friday.app.scene_gate import SceneGate
from friday.app.stall_watch import StallWatch
from friday.app.voice_inputs import VoiceInputs
from friday.brain import gpu_gate
from friday.brain.llm import BrainError
from friday.core.config import LOGS_DIR, Settings
from friday.files.clipboard import read_clipboard
from friday.tools.base import Display, ToolResult

log = logging.getLogger(__name__)

Loader = Callable[..., Components]
TRADING_ON = (
    "Le mode trading vient d'être activé. Annonce-le en une ou deux phrases : les questions "
    "d'analyse partent à Claude seulement après un aperçu à valider ; « fin du mode trading » "
    "pour en sortir."
)
TRADING_OFF = (
    "Le mode trading est désactivé. Dis-le en une phrase : les analyses ne partent plus à "
    "Claude ; calculs, check-list, journal et alertes restent disponibles."
)
TRADING_NO_CLAUDE = (
    "L'utilisateur a demandé le mode trading, mais Claude est désactivé dans les réglages. "
    "Dis-le en une phrase : pas d'analyse par Claude ; calculs, check-list, journal et alertes "
    "marchent sans lui."
)


class Assistant:
    def __init__(
        self, settings: Settings, listener: AssistantListener, loader: Loader = load_components
    ) -> None:
        self.settings = settings
        # Météo (si les scènes sont activées), lieu, globe : la voix attend le fond (U8)
        kinds = {"place", "world", "route", "weather_map", "planes", "space"} | (
            {"weather"} if getattr(settings, "scenes", False) else set()
        )
        self.scene_gate = SceneGate(kinds)
        self.listener = listener
        self._loader = loader
        self.components: Components | None = None
        self.voice_on = settings.tts_enabled
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._waiting_since: float | None = None  # plus ancienne demande pas encore traitée
        self.speech_ended_at = float("-inf")  # fin de la dernière prise de parole (anti-écho)
        self._interrupted = threading.Event()
        self._state: AssistantState | None = None
        self.game = GameMode(self)  # « Friday, mode jeu » : la carte graphique rendue au jeu
        self.inputs = VoiceInputs(settings, self)
        self._reply: Reply | None = None
        self.confirm = ConfirmationGate(listener)  # « Je lance ? » en attente de réponse
        # Fichiers glissés dans la fenêtre, et presse-papier quand la demande en parle
        self.attachments = Attachments(read_clipboard if settings.files_access else None)

    # --- API publique (appelable depuis n'importe quel thread) ---

    def _queue_request(self, event: tuple[str, object]) -> None:
        if self._waiting_since is None:
            self._waiting_since = time.monotonic()
        self._events.put(event)

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True, name="assistant").start()

    @property
    def can_listen(self) -> bool:
        c = self.components
        return bool(c and c.recorder and c.stt)

    def submit_text(self, text: str) -> None:
        if self.game.paused:  # écrire à Friday pendant le mode jeu la fait revenir
            self.game.leave()
        if text.strip() and not self.confirm.route(text):
            self._queue_request(("text", text.strip()))

    def submit_heard(self, text: str) -> None:
        """Demande entendue en mains libres (déjà transcrite)."""
        if not self.confirm.route(text):
            self._queue_request(("heard", text))

    def attach_file(self, path: Path) -> None:
        """Fichier glissé dans la fenêtre : joint à la prochaine demande."""
        self.attachments.add(path)

    def answer_confirmation(self, approved: bool) -> None:
        self.confirm.answer(approved)

    @property
    def busy(self) -> bool:
        return self._state in (AssistantState.THINKING, AssistantState.SPEAKING)

    @property
    def reply_spoken(self) -> str:
        """Ce que Friday a dit dans sa réponse en cours (ou la dernière)."""
        return self._reply.spoken if self._reply else ""

    def start_listening(self) -> None:
        """Push-to-talk : touche ou bouton micro enfoncé."""
        self.inputs.press()

    def stop_listening(self) -> None:
        self.inputs.release()

    def submit_audio(self, audio) -> None:
        """Enregistrement du push-to-talk, à transcrire."""
        self._queue_request(("audio", audio))

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

    def post(self, kind: str, payload: object = None) -> None:
        """Un évènement pour le fil de l'assistant (jeu détecté…)."""
        self._events.put((kind, payload))

    def shutdown(self) -> None:
        self.inputs.close()
        self.interrupt()
        self._events.put(("stop", None))
        brain = getattr(self.components, "brain", None)
        if brain is not None:  # constaté : qwen restait en mémoire vidéo après avoir quitté
            s = self.settings
            gpu_gate.unload_mine(brain.client, (s.ollama_model, s.vision_model, s.embed_model))

    # --- Thread de travail ---

    def _run(self) -> None:
        self.set_state(AssistantState.LOADING)
        try:
            self.components = self._loader(
                self.settings,
                self.listener.on_mic_level,
                self._on_speech_audio,
                on_memory=self.listener.on_memory,
                on_background=lambda task, result: self._events.put(("done", (task, result))),
            )
        except Exception:
            log.exception("Chargement de Friday impossible")
            self.listener.on_notice("Échec du chargement : voir logs/friday.log")
            return
        if self.components.speaker is None:
            self.voice_on = False
        inputs = []
        if self.can_listen:
            self.inputs.start(self.components.stt)
            inputs = self.inputs.describe()
        self.listener.on_ready(describe(self.settings, self.components, inputs))
        self.set_state(AssistantState.IDLE)
        self._events.put(("briefing", None))  # briefing du matin, s'il est dû
        self.game.watch_games()  # mode jeu automatique (G2), si activé
        StallWatch(lambda: self._waiting_since, LOGS_DIR)  # enquête si une demande reste bloquée

        while True:
            kind, payload = self._events.get()
            if kind in ("text", "heard", "audio"):  # prise en charge : plus en attente
                self._waiting_since = None if self._events.empty() else time.monotonic()
            if kind == "stop":
                return
            try:
                self._handle(kind, payload)
            except Exception:
                log.exception("Erreur pendant le traitement de %s", kind)
                self.listener.on_notice("Une erreur est survenue : voir logs/friday.log")
            if not self.inputs.listening and not self.game.paused:
                self.set_state(AssistantState.IDLE)

    def _handle(self, kind: str, payload: object) -> None:
        if kind == "reset":
            self.components.brain.reset()
            self.listener.on_notice("Nouvelle conversation")
        elif kind in ("text", "heard"):
            self.listener.on_user_message(str(payload), by_voice=kind == "heard")
            if self.game.command(str(payload)):
                return
            if not self._trading_command(str(payload)):
                self._respond(self.attachments.wrap(str(payload)), said=str(payload))
        elif kind == "game":  # un jeu vient de se lancer (G2)
            self.game.enter(game=str(payload))
        elif kind == "done":  # une tâche de fond (Claude) est terminée
            if not self.game.keep_for_later(*payload):  # mode jeu : annoncée au retour
                self._announce(*payload)
        elif kind == "briefing" and (request := morning_request(self.components.briefing)):
            self._respond(request)
        elif kind == "audio":
            text = self.components.stt.transcribe(payload)
            if not text:
                self.listener.on_notice("Je n'ai rien entendu")
                return
            if not self.confirm.route(text):
                self.listener.on_user_message(text, by_voice=True)
                if not self._trading_command(text):
                    self._respond(self.attachments.wrap(text), said=text)

    def _trading_command(self, text: str) -> bool:
        """« mode trading » / « fin du mode trading » : reconnu par le code, pas le modèle."""
        trading = self.components.trading
        change = trading.mode.command(text) if trading else None
        if change is None:
            return False
        if change == "on" and trading.job is None:
            self._respond("(Message automatique, pas de l'utilisateur.) " + TRADING_NO_CLAUDE)
            return True
        trading.mode.enabled = change == "on"
        log.info("Mode trading %s", "activé" if trading.mode.enabled else "désactivé")
        self.listener.on_display(Display("trading_mode", "Mode trading",
                                         {"on": trading.mode.enabled}))  # fmt: skip
        self._respond(
            "(Message automatique, pas de l'utilisateur.) "
            + (TRADING_ON if trading.mode.enabled else TRADING_OFF)
        )
        return True

    def _announce(self, task: str, result: ToolResult) -> None:
        """Une tâche de fond est finie : Friday l'annonce de lui-même (`result.text` le guide),
        et une notification Windows s'affiche si sa fenêtre n'est pas au premier plan."""
        if self.settings.notifications:
            from friday.app.notification import notification

            self.listener.on_display(notification(task, result))
        if result.display:
            self.listener.on_display(result.display)
        from friday.app.notification import QUIET

        if task not in QUIET:
            self._respond(f"(Message automatique, pas de l'utilisateur.) {result.text}")

    def _respond(self, text: str, said: str | None = None) -> None:
        """`said` : ce que l'utilisateur a vraiment dit (None pour un message automatique) ;
        c'est lui seul que la mémoire examine, avec la réplique précédente comme contexte."""
        previous = self.reply_spoken
        self._interrupted.clear()
        self.set_state(AssistantState.THINKING)
        speaker = self.components.speaker if self.voice_on else None
        interrupted = False
        self._reply = Reply(self.listener, speaker, self._interrupted, self.confirm.ask,
                            self.scene_gate)  # fmt: skip
        self.listener.on_reply_start()
        stream = self.components.brain.reply(text, self._interrupted.is_set)
        try:
            interrupted = self._reply.run(stream)
            log.info("Réponse : %s", " ".join(self._reply.text.split())[:300])
            self._keep_exchange(said, self._reply.text)
            if not interrupted:
                self.inputs.wake.open_follow_up()  # relance possible sans redire « Friday »
            keeper = self.components.keeper
            if keeper and said and "remember" not in self._reply.tools_used:
                keeper.observe(said, previous)  # mémorisation en arrière-plan
        except BrainError as error:
            if error.looped:  # le modèle s'est mis à se répéter : Ollama l'a arrêté
                self.listener.on_notice(
                    "Je me suis emmêlée dans ma réponse : pouvez-vous reformuler ?"
                )
            else:
                host = self.settings.ollama_host
                self.listener.on_notice(f"Impossible de joindre Ollama sur {host}. Est-il lancé ?")
        finally:
            stream.close()
            self.listener.on_reply_end(interrupted)

    def _keep_exchange(self, said: str | None, reply: str) -> None:
        """Mémoire de la journée : seulement ce que l'utilisateur a vraiment dit."""
        day_log = getattr(self.components, "day_log", None)
        if day_log is None or not said:
            return
        try:
            day_log.add(said, reply)
        except Exception as error:  # ne jamais gêner la conversation
            log.warning("Mémoire de la journée : échange non gardé (%s)", error)

    # --- Utilitaires ---

    def _on_speech_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        if not self.inputs.listening:
            self.set_state(AssistantState.SPEAKING)
        self.listener.on_speech_audio(audio, sample_rate)

    @property
    def speaking(self) -> bool:
        return self._state is AssistantState.SPEAKING

    def set_state(self, state: AssistantState) -> None:
        if self._state is AssistantState.SPEAKING and state is not AssistantState.SPEAKING:
            self.speech_ended_at = time.monotonic()
        if state != self._state:
            self._state = state
            self.listener.on_state(state)
