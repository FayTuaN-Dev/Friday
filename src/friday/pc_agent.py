"""L'agent du PC (R4) : « friday --agent-pc », lancé au démarrage de Windows par une tâche
planifiée, AVANT toute session (deploy/pc/installer.ps1). Le Friday du Pi lui demande :

  GET  /etat      → {"allume": true, "session": …, "ollama": …, "modele_charge": …,
                     "gpu_libre_mo": …}  (le Pi y lit s'il peut penser avec la carte graphique)
  POST /eteindre  {"delai": 60} → Windows s'éteint dans 60 s (annulable)
  POST /annuler   → l'extinction prévue est annulée

Seulement avec la clé du .env (FRIDAY_SERVER_TOKEN, la même que le Pi) ; le pare-feu de
Windows n'ouvre son port qu'au réseau Tailscale (installer.ps1). Bibliothèque standard."""

import hmac
import json
import logging
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

log = logging.getLogger(__name__)
PORT = 8766
OLLAMA = "http://127.0.0.1:11434"
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DELAY = (10, 600)  # l'extinction : entre 10 s et 10 min


def _run(command: list[str]) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=10,
                              creationflags=HIDDEN).stdout  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return ""


def session_open() -> bool:
    """Quelqu'un est-il connecté à Windows ? (le bureau de l'utilisateur tourne)"""
    return "explorer.exe" in _run(["tasklist", "/fi", "imagename eq explorer.exe"]).lower()


def gpu_free_mb() -> int | None:
    out = _run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"])
    try:
        return int(out.split()[0])
    except (IndexError, ValueError):
        return None


def ollama_state(model: str, get=httpx.get) -> tuple[bool, bool]:
    """(Ollama répond ?, `model` est-il déjà en mémoire ?)"""
    try:
        loaded = get(f"{OLLAMA}/api/ps", timeout=3).json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return False, False
    return True, any(m.get("name", "").split(":latest")[0] == model for m in loaded)


def state(model: str) -> dict:
    running, loaded = ollama_state(model)
    return {"allume": True, "session": session_open(), "ollama": running,
            "modele_charge": loaded, "gpu_libre_mo": gpu_free_mb()}  # fmt: skip


def shutdown(delay: int) -> None:
    delay = max(DELAY[0], min(DELAY[1], int(delay)))
    _run(["shutdown", "/s", "/t", str(delay), "/c", "Friday : extinction demandée à distance"])


def cancel_shutdown() -> None:
    _run(["shutdown", "/a"])


def make_handler(token: str, model: str, actions=None):
    """`actions` : (état, éteindre, annuler), remplaçables pour les tests."""
    look, stop, cancel = actions or (lambda: state(model), shutdown, cancel_shutdown)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args) -> None:
            log.debug("%s %s", self.address_string(), fmt % args)

        def _allowed(self) -> bool:
            given = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if token and hmac.compare_digest(given.encode(), token.encode()):
                return True
            self._json(401, {"erreur": "accès refusé"})
            return False

        def _json(self, code: int, data: dict) -> None:
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if not self._allowed():
                return
            if self.path == "/etat":
                self._json(200, look())
            else:
                self._json(404, {})

        def do_POST(self) -> None:
            if not self._allowed():
                return
            size = min(int(self.headers.get("Content-Length") or 0), 1000)
            try:
                data = json.loads(self.rfile.read(size) or b"{}")
            except ValueError:
                data = {}
            if self.path == "/eteindre":
                delay = data.get("delai", 60) if isinstance(data, dict) else 60
                stop(delay if isinstance(delay, int | float) else 60)
                self._json(200, {"ok": True})
            elif self.path == "/annuler":
                cancel()
                self._json(200, {"ok": True})
            else:
                self._json(404, {})

    return Handler


def run_agent(settings) -> None:
    token = os.getenv("FRIDAY_SERVER_TOKEN", "").strip()
    if not token:
        raise SystemExit("FRIDAY_SERVER_TOKEN manquant dans le .env : l'agent ne démarre pas.")
    port = int(os.getenv("FRIDAY_PC_AGENT_PORT", str(PORT)))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler(token, settings.ollama_model))
    log.info("Agent du PC à l'écoute sur le port %d", port)
    httpd.serve_forever()
