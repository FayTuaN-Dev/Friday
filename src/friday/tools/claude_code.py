"""Délégation à Claude Code : le CLI `claude`, connecté au compte de l'utilisateur (Pro),
travaille en arrière-plan dans un dossier dédié. Pas de clé API.
"""

import json
import logging
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from friday.tools.base import Display, Tool, ToolResult

log = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Tu es sollicité par Friday, l'assistant vocal de l'utilisateur. Réponds en français. "
    "Termine par un compte rendu court : ce que tu as fait et les fichiers créés ou modifiés."
)
LLM_MAX_CHARS = 2500
JUST_DONE = 300  # secondes : « annule » juste après la fin → « trop tard », pas « aucune tâche »
# acceptEdits : peut créer et modifier des fichiers du dossier, pas lancer de commandes
DEFAULT_OPTIONS = ("--permission-mode", "acceptEdits")

OnDone = Callable[[str, ToolResult], None]


def snapshot(folder: Path) -> dict[str, float]:
    """Date de modification de chaque fichier, pour repérer ce que Claude a changé."""
    return {
        str(p.relative_to(folder)): p.stat().st_mtime
        for p in folder.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }


class ClaudeCodeJob:
    """Une tâche Claude Code en cours (une seule à la fois)."""

    def __init__(
        self, workspace: Path, model: str, timeout: float,
        options: tuple[str, ...] = DEFAULT_OPTIONS, instructions: str = INSTRUCTIONS,
    ) -> None:  # fmt: skip
        """`options` : droits donnés à Claude (voir trading/analyst.py pour une version isolée)."""
        self.workspace, self.model, self.timeout = workspace, model, timeout
        self.options, self.instructions = options, instructions
        self.task: str | None = None
        self._process: subprocess.Popen | None = None
        # Dernière tâche finie : (consigne, instant de fin, fichiers créés ou modifiés)
        self.last: tuple[str, float, list[str]] | None = None

    @property
    def busy(self) -> bool:
        return self.task is not None

    def run(self, task: str, options: tuple[str, ...] | None = None) -> dict:
        """`options` : droits pour CETTE tâche (sinon ceux du job)."""
        executable = shutil.which("claude")
        if executable is None:
            return {"ok": False, "result": "Le programme « claude » est introuvable."}
        self.workspace.mkdir(parents=True, exist_ok=True)
        before, start = snapshot(self.workspace), time.monotonic()
        command = [
            executable, "-p", task, "--model", self.model, "--output-format", "json",
            *(options or self.options), "--append-system-prompt", self.instructions,
        ]  # fmt: skip
        self._process = subprocess.Popen(
            command, cwd=self.workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )  # fmt: skip
        try:
            out, err = self._process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            self.cancel()
            return {"ok": False, "result": f"Claude n'a pas fini en {self.timeout / 60:.0f} min."}
        finally:
            seconds = round(time.monotonic() - start)
        if self._process.returncode not in (0, None) and not out.strip():
            return {"ok": False, "result": f"Claude s'est arrêté : {err.strip()[:500]}"}
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return {"ok": False, "result": out.strip()[:2000] or "Réponse illisible de Claude."}
        after = snapshot(self.workspace)
        changed = sorted(f for f, mtime in after.items() if before.get(f) != mtime)
        return {
            "ok": not data.get("is_error", False),
            "result": data.get("result", "").strip() or "(pas de compte rendu)",
            "files": changed,
            "seconds": seconds,
        }

    def cancel(self) -> bool:
        process = self._process
        if process and process.poll() is None:
            process.kill()
            return True
        return False


class ClaudeCodeTool(Tool):
    name = "ask_claude_code"
    description = (
        "Confie une tâche à Claude Code, un assistant de programmation très compétent qui "
        "travaille dans le dossier de travail de l'utilisateur : écrire ou modifier du code, des "
        "scripts, créer ou analyser des fichiers, rédiger un long document. À utiliser quand "
        "on te demande de coder, de créer un fichier ou explicitement de demander à Claude. "
        "Écris une consigne complète et précise, en français."
    )
    parameters = {"task": {"type": "string", "description": "La consigne complète pour Claude"}}
    required = ("task",)
    needs_confirmation = True  # consomme le quota de l'utilisateur : il valide d'abord

    def __init__(self, job: ClaudeCodeJob, on_done: OnDone) -> None:
        self.job = job
        self.on_done = on_done

    def label(self, args: dict) -> str:
        return f"🤖 Claude Code : {args.get('task', '')}"

    def confirmation(self, args: dict) -> str:
        task = args.get("task", "").strip().rstrip(".!? ")
        return f"Je confie à Claude la tâche suivante : {task}. Je lance ?"

    def run(self, task: str) -> ToolResult:
        if self.job.busy:
            return ToolResult(f"Claude travaille déjà sur « {self.job.task} ». Propose d'attendre.")
        self.job.task = task
        threading.Thread(target=self._work, args=(task,), daemon=True, name="claude").start()
        return ToolResult(
            "C'est lancé : Claude travaille en arrière-plan, cela peut prendre plusieurs "
            "minutes. Dis-le en une phrase et précise que tu préviendras quand ce sera fini."
        )

    def _work(self, task: str) -> None:
        try:
            outcome = self.job.run(task)
        except Exception as e:
            log.exception("Échec de Claude Code")
            outcome = {"ok": False, "result": f"Erreur : {e}"}
        finally:
            self.job.task = None
        files = outcome.get("files", [])
        self.job.last = (task, time.monotonic(), files)
        text = (
            f"Claude Code a terminé la tâche « {task} » "
            f"({'réussie' if outcome['ok'] else 'échec'}). Son compte rendu :\n"
            f"{outcome['result'][:LLM_MAX_CHARS]}\n"
            f"Fichiers créés ou modifiés : {', '.join(files) or 'aucun'}.\n"
            "Annonce-le à l'utilisateur en une ou deux phrases ; le détail est affiché à l'écran."
        )
        display = Display(
            "claude", task, {**outcome, "files": files, "workspace": str(self.job.workspace)}
        )
        self.on_done(task, ToolResult(text, display))


class CancelClaudeTool(Tool):
    name = "cancel_claude_task"
    description = (
        "Arrête la tâche que Claude Code est en train de faire, si l'utilisateur le demande."
    )
    parameters = {}

    def __init__(self, job: ClaudeCodeJob, clock: Callable[[], float] = time.monotonic) -> None:
        self.job, self.clock = job, clock

    def label(self, args: dict) -> str:
        return "🤖 Arrêt de Claude Code"

    def run(self) -> ToolResult:
        task = self.job.task
        if task and self.job.cancel():
            return ToolResult(f"La tâche « {task} » a été arrêtée.")
        last = self.job.last
        if last and self.clock() - last[1] < JUST_DONE:
            # Constaté : fini 9 s avant « annule », annoncé 10 s après (« aucune tâche »)
            done, ago, files = last[0], round(self.clock() - last[1]), ", ".join(last[2])
            return ToolResult(
                f"Trop tard pour annuler : Claude a déjà terminé « {done} » il y a {ago} s"
                + (f" (fichiers : {files})" if files else "")
                + ". Dis-le en une phrase ; propose de supprimer ces fichiers s'il n'en veut pas."
            )
        return ToolResult("Claude n'avait aucune tâche en cours.")
