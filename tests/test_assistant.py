import pytest
from fakes import (
    SETTINGS,
    EchoTool,
    FakeClient,
    FakeRecorder,
    FakeSTT,
    FakeTTS,
    RecordingListener,
    tool_call,
)

from jarvis.app.assistant import Assistant
from jarvis.app.components import Components
from jarvis.app.events import AssistantState as S
from jarvis.brain.llm import Brain
from jarvis.tools.base import ToolBox
from jarvis.voice.speaker import Speaker

TIMEOUT = 3


@pytest.fixture(autouse=True)
def no_global_keyboard_hook(monkeypatch):
    """Les tests ne doivent pas intercepter le vrai clavier."""
    monkeypatch.setattr("jarvis.voice.ptt.keyboard.hook_key", lambda key, cb: cb)
    monkeypatch.setattr("jarvis.voice.ptt.keyboard.unhook", lambda hook: None)


def make_assistant(chunks=("Il est ", "midi. ", "Bonne journée."), voice=True, ears=False):
    listener = RecordingListener()

    def loader(settings, on_mic_level, on_speech_audio):
        speaker = None
        if voice:
            speaker = Speaker(
                FakeTTS(), play=lambda a, sr: None, stop_playback=lambda: None,
                on_play=on_speech_audio,
            )  # fmt: skip
        return Components(
            brain=Brain(settings, client=FakeClient(chunks=chunks)),
            speaker=speaker,
            stt=FakeSTT() if ears else None,
            recorder=FakeRecorder() if ears else None,
        )

    assistant = Assistant(SETTINGS, listener, loader=loader)
    assistant.voice_on = voice
    assistant.start()
    assert listener.ready.wait(TIMEOUT)
    return assistant, listener


def test_text_message_full_cycle():
    assistant, listener = make_assistant()
    assistant.submit_text("Quelle heure est-il ?")
    assert listener.reply_done.wait(TIMEOUT)
    assistant.shutdown()

    assert listener.of("user") == [("Quelle heure est-il ?", False)]
    assert "".join(c[0] for c in listener.of("chunk")) == "Il est midi. Bonne journée."
    assert listener.of("reply_end") == [(False,)]
    assert len(listener.of("speech")) == 2  # deux phrases prononcées
    states = [s[0] for s in listener.of("state")]
    assert states[:2] == [S.LOADING, S.IDLE]
    assert S.THINKING in states and S.SPEAKING in states


def test_voice_message_by_push_to_talk():
    assistant, listener = make_assistant(voice=False, ears=True)
    assert assistant.can_listen
    assistant.start_listening()
    assert assistant.components.recorder.recording
    assistant.stop_listening()
    assert listener.reply_done.wait(TIMEOUT)
    assistant.shutdown()

    assert listener.of("user") == [("Quelle heure est-il ?", True)]
    states = [s[0] for s in listener.of("state")]
    assert states.index(S.LISTENING) < states.index(S.THINKING)


def test_listening_unavailable_without_microphone():
    assistant, _ = make_assistant(ears=False)
    assistant.start_listening()  # ne doit rien faire ni planter
    assert not assistant.can_listen
    assistant.shutdown()


def test_toggle_voice_and_reset():
    assistant, listener = make_assistant()
    assert assistant.toggle_voice() is False
    assert assistant.toggle_voice() is True
    assistant.reset()
    assert listener.notice_received.wait(TIMEOUT)
    assert listener.of("notice") == [("Nouvelle conversation",)]
    assistant.shutdown()


def test_tool_use_triggers_notice_display_and_filler():
    spoken = []
    listener = RecordingListener()

    def loader(settings, on_mic_level, on_speech_audio):
        client = FakeClient(rounds=[[tool_call("web_search", query="météo")], ["18 degrés."]])
        speaker = Speaker(FakeTTS(), play=lambda a, sr: None, stop_playback=lambda: None)
        speaker.say = spoken.append
        speaker.wait = lambda: None
        return Components(
            brain=Brain(settings, client=client, toolbox=ToolBox([EchoTool()])),
            speaker=speaker,
        )

    assistant = Assistant(SETTINGS, listener, loader=loader)
    assistant.voice_on = True
    assistant.start()
    assert listener.ready.wait(TIMEOUT)
    assistant.submit_text("Quel temps fait-il ?")
    assert listener.reply_done.wait(TIMEOUT)
    assistant.shutdown()

    assert listener.of("tool") == [("🔎 Recherche : météo",)]
    assert listener.of("display") == [("results",)]
    assert len(spoken) == 2  # une phrase d'attente, puis la réponse
    assert spoken[-1] == "18 degrés."
