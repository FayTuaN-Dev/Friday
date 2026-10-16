"""Parler au Friday du Pi depuis le PC (« friday --parle-au-pi "quel temps demain ?" ») :
pour l'essayer avant l'application du téléphone (R3)."""

import json

import httpx

from friday.server.settings import ServerSettings


def talk(server: ServerSettings, text: str, out=print) -> None:
    if not server.pi_url or not server.token:
        out("Réglez FRIDAY_PI_URL et FRIDAY_SERVER_TOKEN dans le .env.")
        return
    headers = {"Authorization": f"Bearer {server.token}"}
    with httpx.stream("POST", f"{server.pi_url}/api/message", json={"texte": text},
                      headers=headers, timeout=300) as response:  # fmt: skip
        if response.status_code != 200:
            out(f"Refusé ({response.status_code}) : {response.read().decode()}")
            return
        for raw in response.iter_lines():
            line = json.loads(raw) if raw.strip() else {}
            if "texte" in line:
                out(line["texte"], end="", flush=True)
            elif "outil" in line:
                out(f"\n[{line['outil']}]", flush=True)
            elif "erreur" in line:
                out(f"\n⚠️ {line['erreur']}")
    out()


def run_server(settings) -> None:
    """« friday --serveur » : le Friday léger, à l'écoute (sur le Pi)."""
    import logging

    from friday.server.http_api import serve
    from friday.server.light_friday import build_light
    from friday.server.settings import load_server_settings

    server = load_server_settings()
    if not server.token:
        raise SystemExit("FRIDAY_SERVER_TOKEN manquant dans le .env : le serveur ne démarre pas "
                         "sans clé.")  # fmt: skip
    log = logging.getLogger(__name__)
    friday = build_light(settings)
    try:  # l'oreille (R3) : la voix du téléphone, transcrite sur le Pi
        from friday.core.config import MODELS_DIR
        from friday.server.ear import Ear

        ear = Ear(server.stt_model, MODELS_DIR, settings.wake_words[0].capitalize())
    except ImportError:
        log.warning("Whisper absent (uv sync --group oreille) : le texte seulement")
        ear = None
    friday.brain.warmup()  # le modèle en mémoire, et ses consignes lues une première fois
    log.info("Modèle : %s", settings.ollama_model)
    serve(friday, server, settings.ollama_model, ear)
