"""Connexion au compte Spotify de l'utilisateur (OAuth « PKCE » : seulement l'identifiant de
l'application, aucun secret). La première fois, le navigateur s'ouvre pour qu'il autorise
Friday ; la clé obtenue est gardée dans data/spotify_token.json (jamais sur GitHub, jamais
dans les sauvegardes) et renouvelée automatiquement."""

import base64
import hashlib
import json
import logging
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

log = logging.getLogger(__name__)

AUTHORIZE = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
PORT = 8888
REDIRECT = f"http://127.0.0.1:{PORT}/callback"  # à déclarer dans l'application Spotify
SCOPES = ("user-modify-playback-state user-read-playback-state playlist-read-private "
          "playlist-read-collaborative user-library-read")  # fmt: skip
SUCCESS = "Friday est connectée à ton compte Spotify. Tu peux fermer cet onglet."
WAIT = 180  # secondes pour accepter dans le navigateur


class NotConnected(Exception):
    """Pas (ou plus) de clé : il faut connecter le compte."""


def challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


class SpotifyAccount:
    def __init__(self, client_id: str, token_path: Path, http=httpx) -> None:
        self.client_id, self.token_path, self.http = client_id.strip(), token_path, http
        self._lock = threading.Lock()
        self._connecting = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.client_id)

    @property
    def connected(self) -> bool:
        return self.token_path.is_file()

    def access_token(self) -> str:
        """Clé valide (renouvelée si besoin) ; NotConnected s'il faut (re)connecter."""
        with self._lock:
            try:
                token = json.loads(self.token_path.read_text("utf-8"))
            except (OSError, ValueError) as error:
                raise NotConnected("compte Spotify non connecté") from error
            if token.get("expires_at", 0) - 60 > time.time():
                return token["access_token"]
            response = self.http.post(TOKEN, data={
                "grant_type": "refresh_token", "refresh_token": token.get("refresh_token", ""),
                "client_id": self.client_id}, timeout=10)  # fmt: skip
            if response.status_code in (400, 401):  # clé révoquée : reconnecter
                self.token_path.unlink(missing_ok=True)
                raise NotConnected("connexion Spotify expirée")
            response.raise_for_status()
            return self._save(response.json(), token.get("refresh_token", ""))

    def _save(self, data: dict, refresh: str = "") -> str:
        token = {"access_token": data["access_token"],
                 "refresh_token": data.get("refresh_token") or refresh,
                 "expires_at": time.time() + int(data.get("expires_in", 3600))}  # fmt: skip
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(token), "utf-8")
        return token["access_token"]

    def authorize_url(self, verifier: str, state: str) -> str:
        return AUTHORIZE + "?" + urlencode({
            "client_id": self.client_id, "response_type": "code", "redirect_uri": REDIRECT,
            "scope": SCOPES, "state": state, "code_challenge_method": "S256",
            "code_challenge": challenge(verifier)})  # fmt: skip

    def connect(self, open_browser=webbrowser.open) -> bool:
        """Ouvre la page d'autorisation et attend la réponse (WAIT s au plus)."""
        verifier, state = secrets.token_urlsafe(64), secrets.token_urlsafe(16)
        received: dict = {}

        class Callback(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (nom imposé par http.server)
                query = parse_qs(urlparse(self.path).query)
                if query.get("state", [""])[0] == state:
                    received.update({k: v[0] for k, v in query.items()})
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                ok = "code" in received
                self.wfile.write((SUCCESS if ok else "Connexion refusée.").encode("utf-8"))

            def log_message(self, *args) -> None:  # pas de bruit dans la console
                pass

        with HTTPServer(("127.0.0.1", PORT), Callback) as server:
            server.timeout = 2
            open_browser(self.authorize_url(verifier, state))
            deadline = time.time() + WAIT
            while not received and time.time() < deadline:
                server.handle_request()
        if "code" not in received:
            log.warning("Connexion Spotify : pas de réponse (%s)", received.get("error", "délai"))
            return False
        response = self.http.post(TOKEN, data={
            "grant_type": "authorization_code", "code": received["code"],
            "redirect_uri": REDIRECT, "client_id": self.client_id,
            "code_verifier": verifier}, timeout=10)  # fmt: skip
        response.raise_for_status()
        self._save(response.json())
        log.info("Compte Spotify connecté")
        return True

    def connect_in_background(self) -> None:
        if not self._connecting.acquire(blocking=False):
            return  # déjà en cours

        def run() -> None:
            try:
                self.connect()
            except Exception:
                log.exception("Connexion Spotify impossible")
            finally:
                self._connecting.release()

        threading.Thread(target=run, daemon=True, name="spotify-connexion").start()
