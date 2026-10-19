"""Faux objets partagés par les tests (aucun modèle, micro ou haut-parleur réel)."""

import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from friday.core.config import Settings
from friday.tools.base import Display, Tool, ToolResult

SETTINGS = Settings(
    user_name="Tony",
    ollama_host="http://localhost:11434",
    ollama_model="qwen3:8b",
    ollama_num_ctx=8192,
    claude_model="sonnet",
    claude_enabled=False,
    claude_workspace=Path("Friday-Workspace"),
    claude_timeout=900.0,
    tts_enabled=False,
    tts_voice="fr_FR-siwis-medium",
    tts_speaker=None,
    tts_speed=1.0,
    stt_enabled=False,
    stt_model="small",
    stt_device="cpu",
    mic_device=None,
    output_device=None,
    ptt_key="home",
    dictation_key="",
    hands_free=False,
    wake_words=["friday"],
    follow_up_seconds=8.0,
    vad_silence_ms=700,
    hands_free_record=False,
    wake_language="fr",
    tts_name_pronunciation="",
    tools_enabled=False,
    search_region="fr-fr",
    search_backend="auto",
    home_city="",
    pc_control=False,
    files_access=False,
    vision_enabled=False,
    vision_model="qwen3-vl:4b-instruct",
    google_enabled=False,
    agenda_enabled=False,
    memory_enabled=False,
    memory_auto=False,
    library_enabled=False,
    embed_model="embeddinggemma",
    log_level="INFO",
    game_auto=False,  # jamais de vraie surveillance des jeux du PC pendant les tests
)


def settings(**changes) -> Settings:
    return replace(SETTINGS, **changes)


def tool_call(name, **arguments):
    """Un appel d'outil tel qu'Ollama le renvoie."""
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


class FakeClient:
    """Imite ollama.Client.chat.

    `chunks` : morceaux de texte d'une réponse simple.
    `rounds` : une liste de réponses successives (une par appel) ; chaque élément est
    un morceau de texte ou un `tool_call(...)`.
    """

    def __init__(self, chunks=(), error=None, rounds=None):
        self.rounds = list(rounds) if rounds is not None else [list(chunks)]
        self.error = error
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if not kwargs.get("stream"):
            return None  # préchargement
        items = self.rounds.pop(0) if self.rounds else []
        return (self._chunk(item) for item in items)

    @staticmethod
    def _chunk(item):
        if isinstance(item, str):
            return SimpleNamespace(message=SimpleNamespace(content=item, tool_calls=None))
        return SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[item]))


class FakeTTS:
    sample_rate = 16000

    def synthesize(self, text):
        return np.full(len(text), 0.1, dtype=np.float32)


class FakeRecorder:
    def __init__(self):
        self.recording = False

    def start(self):
        self.recording = True

    def stop(self):
        self.recording = False
        return np.ones(16000, dtype=np.float32)


class FakeSTT:
    def __init__(self, text="Quelle heure est-il ?"):
        self.text = text

    def transcribe(self, audio):
        return self.text


class RecordingListener:
    """Enregistre tous les événements reçus de l'assistant."""

    def __init__(self):
        self.events = []
        self.ready = threading.Event()
        self.reply_done = threading.Event()
        self.notice_received = threading.Event()
        self.confirm_asked = threading.Event()

    def _log(self, *event):
        self.events.append(event)

    def on_ready(self, info):
        self._log("ready", info)
        self.ready.set()

    def on_state(self, state):
        self._log("state", state)

    def on_user_message(self, text, by_voice):
        self._log("user", text, by_voice)

    def on_reply_start(self):
        self._log("reply_start")

    def on_reply_chunk(self, text):
        self._log("chunk", text)

    def on_reply_end(self, interrupted):
        self._log("reply_end", interrupted)
        self.reply_done.set()

    def on_notice(self, text):
        self._log("notice", text)
        self.notice_received.set()

    def on_tool(self, label):
        self._log("tool", label)

    def on_tool_done(self, ok):
        self._log("tool_done", ok)

    def on_display(self, display):
        self._log("display", display.kind)

    def on_memory(self, text):
        self._log("memory", text)

    def on_confirmation(self, question, seconds=60.0):
        self._log("confirm", question)
        self.confirm_asked.set()

    def on_mic_level(self, level):
        pass

    def on_speech_audio(self, audio, sample_rate):
        self._log("speech", audio.size)

    def of(self, kind):
        return [e[1:] for e in self.events if e[0] == kind]


class EchoTool(Tool):
    """Outil factice : « recherche » qui répond toujours 18 degrés, avec un pop-up."""

    name = "web_search"
    description = "Recherche factice"
    parameters = {"query": {"type": "string"}}
    required = ("query",)

    def label(self, args):
        return f"🔎 Recherche : {args['query']}"

    def run(self, query):
        return ToolResult(
            f"Résultat pour {query} : il fait 18 degrés.",
            Display("results", query, {"results": []}),
        )
