"""Réglages du serveur (dans le .env, à côté des autres)."""

import os
import secrets
from dataclasses import dataclass

DEFAULT_PORT = 8765


@dataclass(frozen=True)
class ServerSettings:
    port: int
    token: str  # vide : le serveur refuse de démarrer (personne ne lui parlerait sans clé)
    pi_url: str  # où joindre le Friday du Pi, vu du PC (« --parle-au-pi »)


def load_server_settings() -> ServerSettings:
    """À appeler après load_settings() (qui lit le .env)."""
    return ServerSettings(
        port=int(os.getenv("FRIDAY_SERVER_PORT", str(DEFAULT_PORT))),
        token=os.getenv("FRIDAY_SERVER_TOKEN", "").strip(),
        pi_url=os.getenv("FRIDAY_PI_URL", "").strip().rstrip("/"),
    )


def new_token() -> str:
    return secrets.token_urlsafe(24)
