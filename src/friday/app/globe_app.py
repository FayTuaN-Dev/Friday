"""Le globe « God's Eye View » (projet MIT de Bilawal Sidhu, installé à part) : son petit
serveur local et sa fenêtre. La fenêtre est Chrome (ou Edge) en mode application, avec un
profil rien qu'à elle : Friday sait ainsi quand elle est fermée, et la ferme elle-même."""

import logging
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import psutil

log = logging.getLogger(__name__)

PORT = 4173
URL = f"http://localhost:{PORT}/"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BROWSERS = ("chrome.exe", "msedge.exe")


def find_browser() -> str | None:
    """Chrome, sinon Edge (chemin donné par Windows, sinon les emplacements habituels)."""
    try:
        import winreg

        for exe in BROWSERS:
            try:
                key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
                    path = winreg.QueryValue(handle, None)
                if path and Path(path).exists():
                    return path
            except OSError:
                continue
    except ImportError:  # hors Windows
        pass
    for root in (r"C:\Program Files", r"C:\Program Files (x86)"):
        for part in (r"Google\Chrome\Application\chrome.exe",
                     r"Microsoft\Edge\Application\msedge.exe"):  # fmt: skip
            if (Path(root) / part).exists():
                return str(Path(root) / part)
    return None


class GlobeApp:
    def __init__(self, folder: Path, profile: Path) -> None:
        self.folder = folder
        self.profile = profile  # profil du navigateur réservé au globe
        self._server: subprocess.Popen | None = None  # lancé par Friday (sinon, on n'y touche pas)

    @property
    def installed(self) -> bool:
        return (self.folder / "node_modules" / "vite" / "bin" / "vite.js").exists()

    def serving(self) -> bool:
        try:
            with urllib.request.urlopen(URL, timeout=1) as response:
                return response.status == 200
        except OSError:
            return False

    def start(self, timeout: float = 45) -> bool:
        """Démarre le serveur du globe s'il ne tourne pas déjà ; True quand il répond."""
        if self.serving():
            return True
        node = shutil.which("node")
        if node is None:
            log.warning("Globe : Node.js introuvable")
            return False
        vite = self.folder / "node_modules" / "vite" / "bin" / "vite.js"
        self._server = subprocess.Popen(
            [node, str(vite), "--host", "localhost", "--port", str(PORT), "--strictPort"],
            cwd=self.folder, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )  # fmt: skip
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.serving():
                return True
            if self._server.poll() is not None:
                break
            time.sleep(0.5)
        log.warning("Globe : le serveur ne répond pas")
        self.stop_server()
        return False

    def open_window(self) -> bool:
        browser = find_browser()
        if browser is None:
            log.warning("Globe : ni Chrome ni Edge trouvé")
            return False
        self.profile.mkdir(parents=True, exist_ok=True)
        subprocess.Popen([browser, f"--app={URL}", f"--user-data-dir={self.profile}",
                          "--no-first-run", "--no-default-browser-check",
                          "--hide-crash-restore-bubble",  # fermée par Friday : rien à restaurer
                          "--window-size=1400,900"], creationflags=NO_WINDOW)  # fmt: skip
        return True

    def _window_processes(self) -> list[psutil.Process]:
        found = []
        marker = str(self.profile).lower()
        for process in psutil.process_iter(["name", "cmdline"]):
            try:
                if (process.info["name"] or "").lower() in BROWSERS and marker in " ".join(
                    process.info["cmdline"] or []
                ).lower():
                    found.append(process)
            except psutil.Error:
                continue
        return found

    def window_open(self) -> bool:
        return bool(self._window_processes())

    def close(self) -> None:
        """Ferme la fenêtre du globe et le serveur lancé par Friday."""
        for process in self._window_processes():
            try:
                process.terminate()
            except psutil.Error:
                pass
        self.stop_server()

    def stop_server(self) -> None:
        if self._server is not None and self._server.poll() is None:
            self._server.terminate()
        self._server = None
