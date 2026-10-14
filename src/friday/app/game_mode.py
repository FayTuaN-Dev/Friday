"""Mode jeu (G1) : « Friday, mode jeu » → elle libère la carte graphique (qwen, Whisper large,
modèles d'Ollama) et ne garde qu'une petite oreille sur le processeur. « Friday, reviens » ou
un double clap → elle recharge tout (10 à 15 s) et revient.

Pendant la pause, les rappels et l'agenda continuent ; ce qui demande le cerveau attend à la
barrière de gpu_gate.py au lieu de recharger un modèle en pleine partie."""

import logging
import re
import subprocess
import threading
import time
from typing import TYPE_CHECKING

import numpy as np

from friday.app.events import AssistantState
from friday.brain import gpu_gate
from friday.tools.base import Display
from friday.voice.recorder import WHISPER_RATE
from friday.voice.wake import normalize

if TYPE_CHECKING:
    from friday.app.assistant import Assistant

log = logging.getLogger(__name__)

ENTER = re.compile(r"\bmode (jeu|gaming|gamer)\b|\bje (vais|pars) (jouer|faire une partie)\b")
NOT_ENTER = re.compile(r"\b(fin|quitte|sors|desactive|arrete|stoppe)\b")
RETURN = re.compile(r"\b(revien\w*|revenir|reveille\w*)\b")
EAR_MODEL = "tiny"  # mesuré : ~0,4 s par phrase sur 2 cœurs ; comprend bien « reviens »
EAR_THREADS = 2  # le jeu garde le reste du processeur
EAR_MAX_SECONDS = 4.0  # « Friday, reviens » est court : une longue phrase (Discord…) est ignorée


def asks_game_mode(text: str) -> bool:
    plain = normalize(text)
    return bool(ENTER.search(plain)) and not NOT_ENTER.search(plain)


def asks_return(text: str) -> bool:
    """« Friday, reviens ». La petite oreille écorche souvent le nom (« Faye des reviens »,
    « Froidé, tu peux revenir ») : un premier mot en « f » suffit, avec « reviens »."""
    plain = normalize(text)
    return bool(RETURN.search(plain)) and (plain.startswith("f") or "friday" in plain)


def vram_used_mb() -> int | None:
    """Mémoire de la carte graphique utilisée (tous programmes), pour le journal."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
        )  # fmt: skip
        return int(out.stdout.split()[0])
    except Exception:
        return None


class PauseEar:
    """La petite oreille du mode jeu : Whisper tiny sur le processeur, phrases courtes seulement."""

    def __init__(self, models_dir) -> None:
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            EAR_MODEL, device="cpu", compute_type="int8", cpu_threads=EAR_THREADS,
            download_root=str(models_dir),
        )  # fmt: skip

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size > EAR_MAX_SECONDS * WHISPER_RATE:
            return ""
        segments, _ = self.model.transcribe(audio, language="fr", beam_size=1, hotwords="Friday",
                                            condition_on_previous_text=False)  # fmt: skip
        return " ".join(s.text for s in segments).strip()


class GameMode:
    def __init__(self, assistant: "Assistant") -> None:
        self.assistant = assistant
        self.paused = False
        self._ear: PauseEar | None = None
        self._lock = threading.Lock()
        self._leaving = False

    # --- Entrée (dans le fil de l'assistant) ---

    def command(self, text: str) -> bool:
        """« Friday, mode jeu » : reconnu par le code (qwen n'y est pour rien)."""
        if self.paused or not asks_game_mode(text):
            return False
        self.enter()
        return True

    def enter(self) -> None:
        a = self.assistant
        name = a.settings.user_name
        self._say(f"Mode jeu : je libère la carte graphique. Dites « Friday, reviens » ou tapez "
                  f"deux fois dans vos mains pour me rappeler. Bonne partie, {name} !")  # fmt: skip
        start, before = time.monotonic(), vram_used_mb()
        self.paused = True
        gpu_gate.OPEN.clear()  # plus aucun modèle ne se recharge pendant la partie
        a.listener.on_display(Display("game_mode", "Mode jeu", {"on": True}))
        a.set_state(AssistantState.PAUSED)
        names = gpu_gate.unload_all(a.components.brain.client)
        if a.components.stt is not None:
            a.components.stt.unload()
        if self._ear is None:
            from friday.core.config import DATA_DIR

            self._ear = PauseEar(DATA_DIR / "models")
        log.info("Mode jeu : %s déchargés en %.1f s ; carte graphique %s → %s Mo",
                 ", ".join(names) or "aucun modèle", time.monotonic() - start, before,
                 vram_used_mb())  # fmt: skip

    # --- Pendant la pause (fil de l'écoute) ---

    def transcribe(self, audio: np.ndarray) -> str:
        return self._ear.transcribe(audio) if self._ear is not None else ""

    def heard(self, text: str) -> None:
        if asks_return(text):
            log.info("Mode jeu : « %s » → retour", text)
            self.leave()
        else:
            log.info("Mode jeu : ignoré « %s »", text)

    def leave(self) -> None:
        """Retour : en arrière-plan (jamais dans le fil de l'écoute ni de l'interface)."""
        with self._lock:
            if not self.paused or self._leaving:
                return
            self._leaving = True
        threading.Thread(target=self._come_back, daemon=True, name="game-mode").start()

    def _come_back(self) -> None:
        a = self.assistant
        start = time.monotonic()
        try:
            self._say(f"Je reviens, {a.settings.user_name}.", wait=False)
            a.listener.on_display(Display("game_mode", "Mode jeu", {"on": False}))
            a.set_state(AssistantState.LOADING)
            gpu_gate.OPEN.set()
            self._reload_in_startup_order()
        finally:
            gpu_gate.OPEN.set()
            self.paused = self._leaving = False
        a.set_state(AssistantState.IDLE)
        log.info("Mode jeu terminé : Friday rechargée en %.1f s", time.monotonic() - start)
        self._say("Me revoilà.", wait=False)

    def _reload_in_startup_order(self) -> None:
        """Le même ordre qu'au démarrage : modèle de la mémoire, qwen, PUIS Whisper. Mesuré :
        Whisper rechargé d'abord, qwen débordait de la carte et lisait 200 jetons/s au lieu
        de 1 550 (carte à 97 %, Friday semblait figée)."""
        a = self.assistant
        settings = a.settings
        if getattr(settings, "memory_enabled", False):
            try:
                a.components.brain.client.embed(model=settings.embed_model, input=["réveil"],
                                                keep_alive="30m")  # fmt: skip
            except Exception as error:
                log.warning("Mode jeu : modèle de la mémoire non rechargé (%s)", error)
        a.components.brain.warmup()
        if a.components.stt is not None:
            a.components.stt.reload()

    def _say(self, text: str, wait: bool = True) -> None:
        """Une phrase dite et affichée, sans passer par qwen."""
        a = self.assistant
        a.listener.on_reply_start()
        a.listener.on_reply_chunk(text)
        a.listener.on_reply_end(False)
        speaker = a.components.speaker if a.voice_on else None
        if speaker is not None:
            speaker.say(text)
            if wait:
                speaker.wait()
