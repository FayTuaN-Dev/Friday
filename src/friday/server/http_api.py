"""L'adresse réseau du Friday léger (R2a, R3). Rien d'autre que la bibliothèque standard.

  GET  /              → l'application du téléphone (web.py)
  GET  /api/etat      → {"pret": true, "modele": …}
  POST /api/message   {"texte": "…"} → la réponse au fil de l'eau, une ligne JSON par
                      morceau : {"texte": …}, {"outil": "🔎 …"}, {"erreur": …}, {"fin": true}
  POST /api/audio     l'enregistrement du bouton maintenu → {"vous": "ce qui a été compris"},
                      puis la réponse comme ci-dessus
  POST /api/nouvelle  → nouvelle conversation

Entrent : le compte Tailscale de l'utilisateur (en-tête ajouté par « tailscale serve », le
serveur n'écoutant que la machine elle-même), ou la clé du .env (« Authorization: Bearer »).
Une seule réponse à la fois (un seul modèle sur le Pi) : les autres attendent leur tour."""

import hmac
import json
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from friday.brain.events import ConfirmationRequest, ToolStarted
from friday.brain.llm import BrainError
from friday.server.ear import MAX_AUDIO
from friday.server.web import web_file

log = logging.getLogger(__name__)
MAX_BODY = 20_000
# Constaté : le petit modèle glisse des émojis malgré ses consignes ; la voix les lirait
EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️‍]")
DEAF = "Je n'ai rien entendu de clair. Pouvez-vous répéter ?"


def lines_of(brain, text: str):
    """Les lignes à envoyer pour une question (sans réseau : testable)."""
    try:
        for event in brain.reply(text):
            if isinstance(event, str):
                if text_ := EMOJI.sub("", event):
                    yield {"texte": text_}
            elif isinstance(event, ToolStarted):
                yield {"outil": event.label}
            elif isinstance(event, ConfirmationRequest):
                event.answer(False)  # pas encore de « oui » à distance : on ne fait rien
                yield {"texte": " (Cette action demande une confirmation, pas encore "
                                "possible à distance.) "}  # fmt: skip
    except BrainError as error:
        log.warning("Réponse impossible : %s", error)
        yield {"erreur": "Le modèle ne répond pas pour le moment."}
    yield {"fin": True}


def heard_lines(brain, ear, audio: bytes):
    """La voix : d'abord ce qui a été compris, puis la réponse."""
    text = ear.hear(audio) if ear is not None else ""
    if not text:
        yield {"erreur": DEAF}
        yield {"fin": True}
        return
    yield {"vous": text}
    yield from lines_of(brain, text)


def make_handler(friday, token: str, model: str, ear=None, tailscale_user: str = ""):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args) -> None:  # dans le journal de Friday, pas la console
            log.debug("%s %s", self.address_string(), fmt % args)

        def _allowed(self) -> bool:
            login = self.headers.get("Tailscale-User-Login", "").strip().lower()
            if tailscale_user and login == tailscale_user:
                return True
            given = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if token and hmac.compare_digest(given.encode(), token.encode()):
                return True
            self._json(401, {"erreur": "accès refusé"})
            return False

        def _send(self, code: int, kind: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data: dict) -> None:
            self._send(code, "application/json; charset=utf-8",
                       json.dumps(data, ensure_ascii=False).encode())  # fmt: skip

        def do_GET(self) -> None:
            if not self._allowed():
                return
            if self.path == "/api/etat":
                self._json(200, {"pret": True, "modele": model})
            elif found := web_file(self.path):
                self._send(200, *found)
            else:
                self._json(404, {"erreur": "inconnu"})

        def do_POST(self) -> None:
            if not self._allowed():
                return
            size = int(self.headers.get("Content-Length") or 0)
            if size > (MAX_AUDIO if self.path == "/api/audio" else MAX_BODY):
                self._json(413, {"erreur": "trop long"})
                return
            body = self.rfile.read(size)
            if self.path == "/api/audio":
                self._stream(lambda: heard_lines(friday.brain, ear, body))
                return
            try:
                data = json.loads(body or b"{}")
            except ValueError:
                self._json(400, {"erreur": "JSON illisible"})
                return
            if self.path == "/api/nouvelle":
                with lock:
                    friday.brain.reset()
                self._json(200, {"ok": True})
            elif self.path == "/api/message" and str(data.get("texte", "")).strip():
                text = str(data["texte"]).strip()
                self._stream(lambda: lines_of(friday.brain, text))
            else:
                self._json(400, {"erreur": "demande incomprise"})

        def _stream(self, lines) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()  # pas de longueur : la connexion se ferme à la fin
            with lock:
                for line in lines():
                    try:
                        self.wfile.write(json.dumps(line, ensure_ascii=False).encode() + b"\n")
                        self.wfile.flush()
                    except OSError:  # l'appelant est parti : on finit la réponse sans lui
                        pass

    return Handler


def serve(friday, server, model: str, ear=None) -> None:
    """`server` : ServerSettings (adresse, port, clé, compte Tailscale)."""
    handler = make_handler(friday, server.token, model, ear, server.tailscale_user)
    httpd = ThreadingHTTPServer((server.host, server.port), handler)
    log.info("Friday léger à l'écoute sur %s:%d", server.host, server.port)
    httpd.serve_forever()
