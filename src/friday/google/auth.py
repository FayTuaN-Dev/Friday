"""Connexion au compte Google de l'utilisateur (OAuth, application de bureau).

La première fois, le navigateur s'ouvre pour qu'il autorise Friday ; la clé obtenue est
gardée dans data/google_token.json (jamais sur GitHub) et renouvelée automatiquement.
"""

import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",  # lire et modifier les événements
    # lire, étiqueter (tri) et mettre à la corbeille ; JAMAIS d'effacement définitif possible
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",  # envoyer (toujours après confirmation)
]
SUCCESS = "Friday est connectée à votre compte Google. Vous pouvez fermer cet onglet."


class NotConnected(Exception):
    """Le message est destiné à l'utilisateur (via le LLM)."""


class GoogleAccount:
    def __init__(self, credentials_path: Path, token_path: Path) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._services: dict = {}
        self._connecting = threading.Lock()

    @property
    def configured(self) -> bool:
        return self.credentials_path.is_file()

    def credentials(self):
        """Clé valide (renouvelée si besoin), ou None s'il faut (re)connecter le compte."""
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        if not self.token_path.is_file():
            return None
        # Sans « SCOPES » ici : on veut les autorisations réellement accordées, pas les voulues
        creds = Credentials.from_authorized_user_file(str(self.token_path))
        if not creds.has_scopes(SCOPES):  # autorisations ajoutées depuis : reconnexion
            log.info("Nouvelles autorisations Google nécessaires : reconnexion")
            return None
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as error:  # autorisation retirée ou expirée
                log.warning("Clé Google refusée (%s) : nouvelle connexion nécessaire", error)
                self.token_path.unlink(missing_ok=True)
                return None
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds
        return None

    @property
    def connected(self) -> bool:
        return self.credentials() is not None

    def connect(self) -> None:
        """Ouvre le navigateur pour l'autorisation (bloquant, 5 min au plus)."""
        from google_auth_oauthlib.flow import InstalledAppFlow

        if not self._connecting.acquire(blocking=False):
            return  # déjà en cours
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300,
                                          success_message=SUCCESS)  # fmt: skip
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
            self._services.clear()
            log.info("Compte Google connecté")
        finally:
            self._connecting.release()

    def disconnect(self) -> None:
        """Oublie la clé : Friday n'a plus accès au compte (jusqu'à une nouvelle connexion)."""
        self.token_path.unlink(missing_ok=True)
        self._services.clear()

    def connect_in_background(self) -> None:
        def work() -> None:
            try:
                self.connect()
            except Exception:
                log.exception("Connexion Google échouée")

        threading.Thread(target=work, daemon=True, name="google-auth").start()

    def service(self, name: str, version: str):
        """Client d'une API Google ; lance l'autorisation si le compte n'est pas connecté."""
        creds = self.credentials()
        if creds is None:
            self.connect_in_background()
            raise NotConnected(
                "Le compte Google n'est pas encore connecté : une page d'autorisation vient "
                "de s'ouvrir dans le navigateur. Une fois accepté, redemande."
            )
        key = (name, version, creds.token)
        if key not in self._services:
            from googleapiclient.discovery import build

            if len(self._services) > 8:  # anciennes clés (renouvelées toutes les heures)
                self._services.clear()
            self._services[key] = build(name, version, credentials=creds, cache_discovery=False)
        return self._services[key]
