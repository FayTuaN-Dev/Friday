"""L'état de Friday et du Pi pour les cartes de côté : les modèles chargés par Ollama (et la
part de chacun sur la carte graphique), et le Friday léger du Pi (/api/etat, avec la clé du
.env). Lu hors du fil de l'interface (ui/desktop/side/sampler.py), toutes les 5 s."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)
GB = 1024**3


@dataclass(frozen=True)
class Model:
    name: str
    vram: float  # Go sur la carte graphique
    size: float  # Go en tout

    @property
    def on_gpu(self) -> float:
        return self.vram / self.size if self.size else 0.0


@dataclass(frozen=True)
class Status:
    models: list[Model] | None = None  # None : Ollama injoignable
    pi: dict | None = None  # None : Pi injoignable (ou pas configuré)
    pi_configured: bool = False


def loaded_models(client) -> list[Model] | None:
    try:
        return [Model(m.model, (m.size_vram or 0) / GB, (m.size or 0) / GB)
                for m in client.ps().models]  # fmt: skip
    except Exception as error:  # Ollama arrêté : la carte le dit
        log.debug("Modèles chargés illisibles : %s", error)
        return None


def pi_status(url: str, token: str, get: Callable = httpx.get) -> dict | None:
    try:
        answer = get(f"{url}/api/etat", headers={"Authorization": f"Bearer {token}"}, timeout=3)
        if answer.status_code != 200:
            return None
        data = answer.json()
        return {"modele": data.get("modele", ""), **data.get("machine", {})}
    except (httpx.HTTPError, ValueError) as error:
        log.debug("Pi injoignable : %s", error)
        return None


class FridayStatus:
    def __init__(self, client, pi_url: str = "", token: str = "", get: Callable = httpx.get):
        self.client, self.pi_url, self.token, self.get = client, pi_url, token, get

    def read(self) -> Status:
        configured = bool(self.pi_url and self.token)
        pi = pi_status(self.pi_url, self.token, self.get) if configured else None
        return Status(loaded_models(self.client), pi, configured)


def from_settings(settings) -> FridayStatus:
    """Le lecteur de l'écran : Ollama du .env, et le Pi s'il est réglé (R1)."""
    import ollama

    from friday.server.settings import load_server_settings

    server = load_server_settings()
    return FridayStatus(ollama.Client(host=settings.ollama_host), server.pi_url, server.token)
