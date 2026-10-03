from datetime import datetime
from types import SimpleNamespace

import ollama
import pytest

from jarvis.brain.conversation import Conversation
from jarvis.brain.llm import Brain, BrainError
from jarvis.brain.prompts import build_system_prompt
from jarvis.core.config import Settings

SETTINGS = Settings(
    user_name="Tony",
    ollama_host="http://localhost:11434",
    ollama_model="qwen3:8b",
    ollama_num_ctx=8192,
    claude_model="sonnet",
    tts_enabled=False,
    tts_voice="fr_FR-tom-medium",
    tts_speaker=None,
    tts_speed=1.0,
    log_level="INFO",
)


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


def test_system_prompt():
    prompt = build_system_prompt("Tony", datetime(2026, 10, 3, 15, 30))
    assert "« Tony »" in prompt
    assert "samedi 3 octobre 2026" in prompt
    assert "15:30" in prompt


def test_conversation_is_trimmed_and_starts_with_user():
    conv = Conversation(max_messages=3)
    for i in range(3):
        conv.add("user", f"q{i}")
        conv.add("assistant", f"r{i}")
    assert conv.messages[0] == {"role": "user", "content": "q2"}
    assert len(conv.messages) == 2


def test_reply_streams_and_remembers():
    client = FakeClient(chunks=["Bonjour", " Tony."])
    brain = Brain(SETTINGS, client=client)

    assert "".join(brain.reply("Salut")) == "Bonjour Tony."
    assert brain.conversation.messages == [
        {"role": "user", "content": "Salut"},
        {"role": "assistant", "content": "Bonjour Tony."},
    ]
    sent = client.calls[0]
    assert sent["messages"][0]["role"] == "system"
    assert sent["think"] is False


def test_reply_error_forgets_question():
    brain = Brain(SETTINGS, client=FakeClient(error=ConnectionError("down")))
    with pytest.raises(BrainError):
        list(brain.reply("Salut"))
    assert brain.conversation.messages == []

    brain.client = FakeClient(error=ollama.ResponseError("model not found"))
    with pytest.raises(BrainError):
        list(brain.reply("Salut"))


def test_warmup_never_raises():
    Brain(SETTINGS, client=FakeClient(error=ConnectionError("down"))).warmup()
