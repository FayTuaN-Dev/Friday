# Jarvis

Assistant personnel vocal de bureau, 100 % local par défaut : on lui parle, il répond à voix haute
et affiche le chat, des images et des résultats dans des pop-ups.

- **Cerveau** : Ollama (`qwen3:8b`), avec délégation à Claude Code pour le code
- **Voix** : faster-whisper (écoute) + Piper (parole)
- **Interface** : PySide6

Voir [ROADMAP.md](ROADMAP.md) pour les fonctionnalités et l'avancement.

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/) et [Ollama](https://ollama.com) avec le modèle `qwen3:8b`.

```
ollama pull qwen3:8b
uv sync
copy .env.example .env
```

## Utilisation

```
uv run jarvis
```

Commandes dans le chat : `/voix` (activer/couper la voix), `/reset` (nouvelle conversation), `/quit` (quitter).

Pour comparer les voix disponibles : `uv run python -m jarvis.voice.audition`, puis régler `TTS_VOICE` dans `.env`.

## Développement

Une branche par brique, une PR vers `main`, merge quand la CI est verte.

```
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # mise en forme
```
