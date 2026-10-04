"""Outils : ouvrir et fermer des applications."""

import subprocess
from pathlib import PureWindowsPath

from friday.tools.base import Tool, ToolResult
from friday.tools.pc import windows
from friday.tools.pc.apps_index import AppIndex

GENERIC_WORDS = {"google", "microsoft", "windows", "visual", "studio", "the"}


def launch(app_id: str) -> None:
    """Fonctionne pour les applications classiques comme pour celles du Store."""
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])


class OpenAppTool(Tool):
    name = "open_app"
    description = (
        "Ouvre une application installée sur l'ordinateur (Spotify, Discord, Chrome, Steam, "
        "calculatrice, bloc-notes, explorateur de fichiers, paramètres…)."
    )
    parameters = {"app": {"type": "string", "description": "Nom de l'application"}}
    required = ("app",)

    def __init__(self, index: AppIndex, launcher=launch) -> None:
        self.index = index
        self.launcher = launcher

    def label(self, args: dict) -> str:
        return f"🚀 Ouverture : {args.get('app', '')}"

    def run(self, app: str) -> ToolResult:
        found = self.index.find(app)
        if found is None:
            ideas = ", ".join(self.index.suggestions(app)) or "aucune"
            return ToolResult(f"Application « {app} » introuvable. Proches : {ideas}.")
        self.launcher(found.app_id)
        return ToolResult(f"{found.name} est en train de s'ouvrir.")


class CloseAppTool(Tool):
    name = "close_app"
    description = (
        "Ferme une application ouverte (comme un clic sur la croix : elle peut proposer "
        "d'enregistrer). À utiliser quand l'utilisateur demande de fermer ou quitter une appli."
    )
    parameters = {"app": {"type": "string", "description": "Nom de l'application"}}
    required = ("app",)
    needs_confirmation = True  # fermer peut faire perdre un travail en cours

    def __init__(self, index: AppIndex) -> None:
        self.index = index

    def label(self, args: dict) -> str:
        return f"✖ Fermeture : {args.get('app', '')}"

    def confirmation(self, args: dict) -> str:
        return f"Je ferme {args.get('app', 'cette application')} ?"

    def run(self, app: str) -> ToolResult:
        processes = {p.pid: p for name in self._process_names(app)
                     for p in windows.find_processes(name)}  # fmt: skip
        if not processes:
            return ToolResult(f"{app} ne semble pas ouvert.")
        closed = windows.close_windows(set(processes))
        if not closed:
            return ToolResult(f"{app} tourne, mais sans fenêtre à fermer (arrière-plan).")
        return ToolResult(f"{app} : fermeture demandée ({closed} fenêtre(s)).")

    def _process_names(self, app: str) -> set[str]:
        """« Google Chrome » → {google chrome, chrome} ; l'AppID peut donner le .exe exact."""
        names = {app}
        found = self.index.find(app)
        if found:
            names.add(found.name)
            if found.app_id.lower().endswith(".exe"):
                names.add(PureWindowsPath(found.app_id).stem)
            names |= {w for w in found.name.split() if len(w) >= 4}
        return {n for n in names if n.lower() not in GENERIC_WORDS}
