"""Faux objets partagés par les tests (aucun modèle, micro ou haut-parleur réel)."""

import threading
from dataclasses import replace
from types import SimpleNamespace

import numpy as np

from jarvis.core.config import Settings

SETTINGS = Settings(
    user_name="Tony",
    ollama_host="http://localhost:11434",
    ollama_model="qwen3:8b",
    ollama_num_ctx=8192,
    claude_model="sonnet",
    tts_enabled=False,
    tts_voice="fr_FR-siwis-medium",
    tts_speaker=None,
    tts_speed=1.0,
    stt_enabled=False,
    stt_model="small",
    stt_device="cpu",
    mic_device=None,
    ptt_key="home",
    log_level="INFO",
)


def settings(**changes) -> Settings:
    return replace(SETTINGS, **changes)


class FakeClient:
    """Imite ollama.Client.chat en renvoyant des morceaux prédéfinis."""

    def __init__(self, chunks=(), error=None):
        self.chunks = chunks
        self.error = error
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return (SimpleNamespace(message=SimpleNamespace(content=c)) for c in self.chunks)


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

    def on_mic_level(self, level):
        pass

    def on_speech_audio(self, audio, sample_rate):
        self._log("speech", audio.size)

    def of(self, kind):
        return [e[1:] for e in self.events if e[0] == kind]
