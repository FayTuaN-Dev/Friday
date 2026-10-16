"""L'adresse réseau du Friday léger (R2a). Rien d'autre que la bibliothèque standard.

  GET  /api/etat      → {"pret": true, "modele": …}
  POST /api/message   {"texte": "…"} → la réponse au fil de l'eau, une ligne JSON par
                      morceau : {"texte": …}, {"outil": "🔎 …"}, {"erreur": …}, {"fin": true}
  POST /api/nouvelle  → nouvelle conversation

Chaque demande porte la clé du .env (« Authorization: Bearer … ») : sans elle, refus.
Une seule réponse à la fois (un seul modèle sur le Pi) : les autres attendent leur tour."""

import hmac
import json
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from friday.brain.events import ConfirmationRequest, ToolStarted
from friday.brain.llm import BrainError

log = logging.getLogger(__name__)
MAX_BODY = 20_000
# Constaté : le petit modèle glisse des émojis malgré ses consignes ; la voix les lirait
EMOJI = re.compile("[🀀-🫿☀-➿️‍]")


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


def make_handler(friday, token: str, model: str):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args) -> None:  # dans le journal de Friday, pas la console
            log.debug("%s %s", self.address_string(), fmt % args)

        def _allowed(self) -> bool:
            given = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if token and hmac.compare_digest(given.encode(), token.encode()):
                return True
            self._json(401, {"erreur": "clé manquante ou fausse"})
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
            if self.path == "/api/etat":
                self._json(200, {"pret": True, "modele": model})
            else:
                self._json(404, {"erreur": "inconnu"})

        def do_POST(self) -> None:
            if not self._allowed():
                return
            size = int(self.headers.get("Content-Length") or 0)
            if size > MAX_BODY:
                self._json(413, {"erreur": "trop long"})
                return
            try:
                data = json.loads(self.rfile.read(size) or b"{}")
            except ValueError:
                self._json(400, {"erreur": "JSON illisible"})
                return
            if self.path == "/api/nouvelle":
                with lock:
                    friday.brain.reset()
                self._json(200, {"ok": True})
            elif self.path == "/api/message" and str(data.get("texte", "")).strip():
                self._stream(str(data["texte"]).strip())
            else:
                self._json(400, {"erreur": "demande incomprise"})

        def _stream(self, text: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.end_headers()  # pas de longueur : la connexion se ferme à la fin
            with lock:
                for line in lines_of(friday.brain, text):
                    try:
                        self.wfile.write(json.dumps(line, ensure_ascii=False).encode() + b"\n")
                        self.wfile.flush()
                    except OSError:  # l'appelant est parti : on finit la réponse sans lui
                        pass

    return Handler


def serve(friday, token: str, port: int, model: str) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(friday, token, model))
    log.info("Friday léger à l'écoute sur le port %d", port)
    server.serve_forever()
