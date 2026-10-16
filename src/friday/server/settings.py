"""Réglages du serveur (dans le .env, à côté des autres)."""

import os
import secrets
from dataclasses import dataclass

DEFAULT_PORT = 8765


@dataclass(frozen=True)
class ServerSettings:
    port: int
    token: str  # la clé (le PC, « --parle-au-pi ») ; vide : le serveur ne démarre pas
    pi_url: str  # où joindre le Friday du Pi, vu du PC
    # 127.0.0.1 : joignable seulement par « tailscale serve » (HTTPS), pas par le réseau local
    host: str = "127.0.0.1"
    # Le compte Tailscale de l'utilisateur (« Tailscale-User-Login », ajouté par tailscale
    # serve) : son téléphone entre sans clé à taper
    tailscale_user: str = ""
    stt_model: str = "base"  # Whisper sur le Pi : « base » 2,7 s par phrase, « small » 8 s


def load_server_settings() -> ServerSettings:
    """À appeler après load_settings() (qui lit le .env)."""
    return ServerSettings(
        port=int(os.getenv("FRIDAY_SERVER_PORT", str(DEFAULT_PORT))),
        token=os.getenv("FRIDAY_SERVER_TOKEN", "").strip(),
        pi_url=os.getenv("FRIDAY_PI_URL", "").strip().rstrip("/"),
        host=os.getenv("FRIDAY_SERVER_HOST", "127.0.0.1").strip(),
        tailscale_user=os.getenv("FRIDAY_TAILSCALE_USER", "").strip().lower(),
        stt_model=os.getenv("FRIDAY_PI_STT_MODEL", "base").strip(),
    )


def new_token() -> str:
    return secrets.token_urlsafe(24)
