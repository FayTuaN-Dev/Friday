from datetime import datetime

import ollama
import pytest
from fakes import SETTINGS, FakeClient

from jarvis.brain.conversation import Conversation
from jarvis.brain.llm import Brain, BrainError
from jarvis.brain.prompts import build_system_prompt


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


def test_interrupted_reply_keeps_history_alternating():
    brain = Brain(SETTINGS, client=FakeClient(chunks=["Je vais", " vous", " expliquer."]))
    stream = brain.reply("Explique")
    next(stream)
    stream.close()  # interruption après le premier morceau
    assert brain.conversation.messages == [
        {"role": "user", "content": "Explique"},
        {"role": "assistant", "content": "Je vais […]"},
    ]
