import json
import threading
import time
from types import SimpleNamespace

import pytest
from fakes import SETTINGS, FakeClient, RecordingListener, tool_call

from friday.app.assistant import Assistant
from friday.app.components import Components
from friday.app.confirmations import ConfirmationGate, classify
from friday.brain.events import ConfirmationRequest, ToolFinished, ToolStarted
from friday.brain.llm import Brain
from friday.tools import claude_code
from friday.tools.base import Tool, ToolBox, ToolResult
from friday.tools.claude_code import CancelClaudeTool, ClaudeCodeJob, ClaudeCodeTool

TIMEOUT = 5


@pytest.fixture(autouse=True)
def no_global_keyboard_hook(monkeypatch):
    monkeypatch.setattr("friday.voice.ptt.keyboard.hook_key", lambda key, cb: cb)
    monkeypatch.setattr("friday.voice.ptt.keyboard.unhook", lambda hook: None)


# --- Confirmation ---


def test_confirmation_request_answer_timeout_and_cancel():
    request = ConfirmationRequest("x", {}, "Je lance ?")
    threading.Timer(0.05, lambda: request.answer(True)).start()
    assert request.wait(timeout=2) is True

    assert ConfirmationRequest("x", {}, "?").wait(timeout=0.2) is False  # pas de réponse
    assert ConfirmationRequest("x", {}, "?").wait(timeout=5, cancelled=lambda: True) is False


@pytest.mark.parametrize(
    ("text", "verdict"),
    [
        ("Oui", "yes"),
        ("Oui vas-y !", "yes"),
        ("D'accord, lance-le", "yes"),
        ("C'est parti", "yes"),
        ("Non", "no"),
        ("Laisse tomber.", "no"),
        ("Plutôt demande-lui un script en Rust", "other"),
    ],
)
def test_classify_answers(text, verdict):
    assert classify(text) == verdict


def test_gate_routes_answers_only_while_waiting():
    listener = RecordingListener()
    gate = ConfirmationGate(listener)
    assert gate.route("oui") is False  # rien en attente : message normal

    request = ConfirmationRequest("x", {}, "Je lance ?")
    gate.ask(request)
    assert listener.of("confirm") == [("Je lance ?",)]
    assert gate.waiting and gate.route("Oui, vas-y") is True
    assert request.approved and not gate.waiting

    other = ConfirmationRequest("x", {}, "Je lance ?")
    gate.ask(other)
    assert gate.route("Non, cherche plutôt la météo") is True  # « non » : consommé
    assert not other.approved


class Sensitive(Tool):
    name = "sensitive"
    description = "action sensible"
    parameters = {}
    needs_confirmation = True

    def __init__(self):
        self.runs = 0

    def run(self):
        self.runs += 1
        return ToolResult("fait")


@pytest.mark.parametrize("approved", [True, False])
def test_brain_waits_for_confirmation_before_running(approved):
    tool = Sensitive()
    client = FakeClient(rounds=[[tool_call("sensitive")], ["Terminé."]])
    brain = Brain(SETTINGS, client=client, toolbox=ToolBox([tool]))

    events = []
    for event in brain.reply("Fais-le"):
        events.append(event)
        if isinstance(event, ConfirmationRequest):
            event.answer(approved)

    assert isinstance(events[0], ConfirmationRequest)
    assert tool.runs == (1 if approved else 0)
    assert any(isinstance(e, ToolStarted) for e in events) is approved
    finished = next(e for e in events if isinstance(e, ToolFinished))
    assert ("n'a pas confirmé" in finished.result.text) is (not approved)


def test_toolbox_uses_tool_timeout_and_cancels():
    class Slow(Tool):
        name, description, parameters, timeout = "slow", "lent", {}, 0.2
        cancelled = False

        def run(self):
            time.sleep(5)

        def cancel(self):
            self.cancelled = True

    slow = Slow()
    assert "pas répondu à temps" in ToolBox([slow]).run("slow", {}).text
    assert slow.cancelled


# --- Claude Code ---


class FakeProcess:
    def __init__(self, workspace, payload, returncode=0, writes=()):
        self.workspace, self.payload, self.returncode, self.writes = workspace, payload, 0, writes
        self.killed = False

    def communicate(self, timeout):
        for name in self.writes:
            (self.workspace / name).write_text("print('bonjour')")
        return self.payload, ""

    def poll(self):
        return None

    def kill(self):
        self.killed = True


def fake_claude(monkeypatch, tmp_path, payload, writes=()):
    calls = []

    def popen(command, cwd, **kwargs):
        calls.append(SimpleNamespace(command=command, cwd=cwd))
        return FakeProcess(tmp_path, payload, writes=writes)

    monkeypatch.setattr(claude_code.shutil, "which", lambda name: "claude.exe")
    monkeypatch.setattr(claude_code.subprocess, "Popen", popen)
    return calls


def test_job_runs_claude_in_workspace_and_lists_changed_files(monkeypatch, tmp_path):
    payload = json.dumps({"result": "J'ai créé **bonjour.py**.", "is_error": False})
    calls = fake_claude(monkeypatch, tmp_path, payload, writes=["bonjour.py"])
    outcome = ClaudeCodeJob(tmp_path, "sonnet", 60).run("Écris un script bonjour")

    assert outcome["ok"] and "bonjour.py" in outcome["result"]
    assert outcome["files"] == ["bonjour.py"]
    command = calls[0].command
    assert command[:3] == ["claude.exe", "-p", "Écris un script bonjour"]
    assert "acceptEdits" in command and calls[0].cwd == tmp_path


def test_job_handles_missing_cli_and_bad_output(monkeypatch, tmp_path):
    monkeypatch.setattr(claude_code.shutil, "which", lambda name: None)
    assert "introuvable" in ClaudeCodeJob(tmp_path, "sonnet", 60).run("x")["result"]
    fake_claude(monkeypatch, tmp_path, "pas du json")
    assert ClaudeCodeJob(tmp_path, "sonnet", 60).run("x")["result"] == "pas du json"


class FakeJob:
    def __init__(self, workspace="W"):
        self.workspace, self.task, self.release = workspace, None, threading.Event()
        self.cancelled = False

    @property
    def busy(self):
        return self.task is not None

    def run(self, task):
        self.release.wait(TIMEOUT)
        return {"ok": True, "result": "Fait.", "files": ["a.py"], "seconds": 3}

    def cancel(self):
        self.cancelled = True
        return True


def test_tool_runs_in_background_and_reports_when_done():
    done, job = [], FakeJob()
    tool = ClaudeCodeTool(job, lambda task, result: done.append((task, result)))
    first = tool.run("Écris a.py")
    assert "arrière-plan" in first.text and job.busy
    assert "déjà" in tool.run("Autre chose").text  # une seule tâche à la fois
    assert "arrêtée" in CancelClaudeTool(job).run().text and job.cancelled
    job.release.set()
    for _ in range(50):
        if done:
            break
        time.sleep(0.05)
    task, result = done[0]
    assert task == "Écris a.py" and "a.py" in result.text
    assert result.display.kind == "claude" and not job.busy
    assert "confie à Claude" in tool.confirmation({"task": "Écris a.py"})


def test_assistant_confirms_by_voice_then_announces_completion():
    listener, job = RecordingListener(), FakeJob()

    def loader(settings, on_mic_level, on_speech_audio, on_background=None, **_):
        tool = ClaudeCodeTool(job, on_background)
        client = FakeClient(
            rounds=[
                [tool_call("ask_claude_code", task="Écris a.py")],
                ["C'est lancé."],
                ["Claude a fini a.py."],
            ]
        )
        return Components(brain=Brain(settings, client=client, toolbox=ToolBox([tool])))

    assistant = Assistant(SETTINGS, listener, loader=loader)
    assistant.start()
    assert listener.ready.wait(TIMEOUT)
    assistant.submit_text("Demande à Claude d'écrire a.py")
    assert listener.confirm_asked.wait(TIMEOUT)
    assistant.submit_text("oui")  # la réponse va à la confirmation, pas au LLM
    assert listener.reply_done.wait(TIMEOUT)
    listener.reply_done.clear()
    job.release.set()  # Claude termine
    assert listener.reply_done.wait(TIMEOUT)  # Friday l'annonce de lui-même
    assistant.shutdown()

    assert [u[0] for u in listener.of("user")] == ["Demande à Claude d'écrire a.py"]
    assert listener.of("display") == [("claude",)]
    chunks = "".join(c[0] for c in listener.of("chunk"))
    assert "C'est lancé." in chunks and "Claude a fini a.py." in chunks
