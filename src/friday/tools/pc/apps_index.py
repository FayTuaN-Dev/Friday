"""Index des applications installées, comme le menu Démarrer de Windows (Get-StartApps)."""

import difflib
import json
import logging
import subprocess
import threading
from dataclasses import dataclass

from friday.voice.wake import normalize

log = logging.getLogger(__name__)

# Noms français courants → nom (souvent anglais) dans le menu Démarrer
ALIASES = {
    "calculatrice": "calculator",
    "bloc notes": "notepad",
    "bloc note": "notepad",
    "explorateur": "explorateur de fichiers",
    "fichiers": "explorateur de fichiers",
    "reglages": "parametres",
    "parametre": "parametres",
    "navigateur": "google chrome",
    "chrome": "google chrome",
    "vscode": "visual studio code",
    "vs code": "visual studio code",
}
# Entrées du menu Démarrer qui ne sont pas des applications
NOT_APPS = (".html", ".htm", ".txt", ".url", ".pdf", ".chm", ".md")
SKIP_WORDS = ("uninstall", "desinstaller", "release notes", "readme", "documentation")


@dataclass(frozen=True)
class App:
    name: str
    app_id: str


def load_start_apps() -> list[App]:
    command = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"
    )
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).stdout  # fmt: skip
    entries = json.loads(out or "[]")
    entries = [entries] if isinstance(entries, dict) else entries
    return [
        App(e["Name"], e["AppID"])
        for e in entries
        if not e["AppID"].lower().endswith(NOT_APPS)
        and not any(w in normalize(e["Name"]) for w in SKIP_WORDS)
    ]


class AppIndex:
    def __init__(self, loader=load_start_apps) -> None:
        self._loader = loader
        self._apps: list[App] | None = None
        self._lock = threading.Lock()

    @property
    def apps(self) -> list[App]:
        with self._lock:
            if self._apps is None:  # chargé au premier besoin (~2 s), puis gardé
                self._apps = self._loader()
                log.info("%d applications indexées", len(self._apps))
            return self._apps

    def refresh(self) -> None:
        with self._lock:
            self._apps = None

    def find(self, query: str) -> App | None:
        """La meilleure correspondance : nom exact, puis début, puis mot, puis ressemblance."""
        wanted = normalize(query)
        wanted = ALIASES.get(wanted, wanted)
        names = {normalize(a.name): a for a in self.apps}
        if wanted in names:
            return names[wanted]
        for test in (
            lambda n: n.startswith(wanted),
            lambda n: wanted in n.split() or f" {wanted}" in f" {n}",
        ):
            matches = sorted((n for n in names if test(n)), key=len)
            if matches:
                return names[matches[0]]
        close = difflib.get_close_matches(wanted, list(names), n=1, cutoff=0.75)
        return names[close[0]] if close else None

    def suggestions(self, query: str, n: int = 3) -> list[str]:
        names = {normalize(a.name): a.name for a in self.apps}
        close = difflib.get_close_matches(normalize(query), list(names), n=n, cutoff=0.4)
        return [names[c] for c in close]
