# Friday léger sur le Raspberry Pi

Friday tourne sans fenêtre sur le Pi (`friday --serveur`), avec un petit modèle
(`qwen3:4b-instruct-2507-q4_K_M`) et des consignes courtes (voir `src/friday/brain/light.py`).

## Installation (une fois)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh          # uv, dans ~/.local/bin
git clone git@github.com:FayTuaN-Dev/Friday.git ~/friday  # clé de déploiement en lecture seule
cd ~/friday && uv sync --no-default-groups                # sans la fenêtre ni le micro
ollama pull qwen3:4b-instruct-2507-q4_K_M && ollama pull embeddinggemma
sudo cp deploy/pi/friday.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now friday
```

Ollama doit pouvoir garder 2 modèles (la conversation et la mémoire) :
`/etc/systemd/system/ollama.service.d/friday.conf` → `OLLAMA_MAX_LOADED_MODELS=2`.

## Le `.env` du Pi

```
FRIDAY_USER_NAME=…
HOME_CITY=…
OLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M
OLLAMA_NUM_CTX=4096
FRIDAY_SERVER_TOKEN=…   # la clé : sans elle, le serveur refuse tout
```

Et dans le `.env` du PC, pour lui parler (`uv run friday --parle-au-pi "quel temps demain ?"`) :

```
FRIDAY_PI_URL=http://<adresse Tailscale du Pi>:8765
FRIDAY_SERVER_TOKEN=…   # la même clé
```

## Mettre à jour

```bash
cd ~/friday && git pull && uv sync --no-default-groups && sudo systemctl restart friday
```

Journal : `journalctl -u friday -f` (et `~/friday/logs/`).
