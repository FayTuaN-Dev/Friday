# Friday léger sur le Raspberry Pi

Friday tourne sans fenêtre sur le Pi (`friday --serveur`), avec un petit modèle
(`qwen3:4b-instruct-2507-q4_K_M`) et des consignes courtes (voir `src/friday/brain/light.py`).

## Installation (une fois)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh          # uv, dans ~/.local/bin
git clone git@github.com:FayTuaN-Dev/Friday.git ~/friday  # clé de déploiement en lecture seule
cd ~/friday && uv sync --no-default-groups --group oreille  # sans fenêtre ; Whisper oui
ollama pull qwen3:4b-instruct-2507-q4_K_M && ollama pull embeddinggemma
sudo cp deploy/pi/friday.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now friday
sudo tailscale serve --bg http://127.0.0.1:8765          # HTTPS, pour le téléphone
```

Le serveur n'écoute que le Pi lui-même (127.0.0.1) : on le joint par `tailscale serve`, en
HTTPS (`https://<nom du Pi>.<réseau>.ts.net`). Le téléphone entre grâce au compte Tailscale de
l'utilisateur (`FRIDAY_TAILSCALE_USER`), le PC avec la clé (`FRIDAY_SERVER_TOKEN`).

## L'application du téléphone

Ouvrir `https://<nom du Pi>.<réseau>.ts.net` dans Chrome (Tailscale activé), puis menu ⋮ →
« Ajouter à l'écran d'accueil ». Maintenir le bouton orange pour parler.

Ollama doit pouvoir garder 2 modèles (la conversation et la mémoire) :
`/etc/systemd/system/ollama.service.d/friday.conf` → `OLLAMA_MAX_LOADED_MODELS=2`.

## Le `.env` du Pi

```
FRIDAY_USER_NAME=…
HOME_CITY=…
OLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M
OLLAMA_NUM_CTX=4096
FRIDAY_SERVER_TOKEN=…   # la clé : sans elle, le serveur refuse tout
FRIDAY_TAILSCALE_USER=… # le compte Tailscale de l'utilisateur (son téléphone entre sans clé)
```

Et dans le `.env` du PC, pour lui parler (`uv run friday --parle-au-pi "quel temps demain ?"`) :

```
FRIDAY_PI_URL=https://<nom du Pi>.<réseau>.ts.net
FRIDAY_SERVER_TOKEN=…   # la même clé
```

## Mettre à jour

```bash
cd ~/friday && git pull && sudo systemctl restart friday
```

Journal : `journalctl -u friday -f` (et `~/friday/logs/`).
