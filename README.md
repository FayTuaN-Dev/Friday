# Jarvis

Assistant personnel vocal de bureau, 100 % local par défaut : on lui parle, il répond à voix haute
et affiche le chat, des images et des résultats dans des pop-ups.

<p align="center"><img src="docs/images/interface.png" width="360" alt="Interface de Jarvis"></p>

- **Cerveau** : Ollama (`qwen3:8b`), avec délégation à Claude Code pour le code
- **Voix** : faster-whisper (écoute) + Piper (parole)
- **Interface** : PySide6
- **Mémoire** : se souvient de vous d'une session à l'autre (SQLite local + embeddings `embeddinggemma`)
- **Outils** : météo (Open-Meteo), recherche web, lecture de pages et images, sans clé API, affichés en pop-ups

Voir [ROADMAP.md](ROADMAP.md) pour les fonctionnalités et l'avancement, et
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour l'organisation du code.

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/) et [Ollama](https://ollama.com) avec le modèle `qwen3:8b`.

```
ollama pull qwen3:8b
ollama pull embeddinggemma
uv sync
copy .env.example .env
```

## Utilisation

```
uv run jarvis          # application de bureau
uv run jarvis --cli    # version terminal
```

- **Mains libres** : dire « **Jarvis**, quelle heure est-il ? » d'une traite. « Jarvis » seul → il répond « Oui ? » et écoute la suite. Juste après une réponse, on peut relancer sans redire son nom. Pendant qu'il parle : « Jarvis, … » lui coupe la parole, « stop » le fait taire.
- **Mémoire** : il retient seul ce qui compte (« 🧠 Mémorisé : … »). « Retiens que… », « Oublie que… », « Qu'est-ce que tu sais sur moi ? »
- **Claude Code** : « Jarvis, demande à Claude d'écrire… » → il demande confirmation (« oui », ou bouton), Claude travaille en arrière-plan dans `CLAUDE_WORKSPACE`, et Jarvis prévient quand c'est fini. Utilise le CLI `claude` connecté au compte Pro, sans clé API.
- **Push-to-talk** : maintenir la touche `Début` (réglable via `PTT_KEY`), parler, relâcher.
- **Écrire** : taper son message puis Entrée.

Dans la fenêtre, les boutons de la barre du bas permettent d'envoyer, de parler (maintenir 🎙), de couper la voix et de démarrer une nouvelle conversation. En mode terminal : `/voix` (activer/couper la voix), `/reset` (nouvelle conversation), `/quit` (quitter).

Choisir le micro : `uv run python -m sounddevice` liste les périphériques, puis régler `MIC_DEVICE` (numéro ou morceau du nom).

Choisir la sortie audio : `OUTPUT_DEVICE` (même principe). En cas de grésillements : `uv run python -m jarvis.voice.diagnostic`.

Pour comparer les voix disponibles : `uv run python -m jarvis.voice.audition`, puis régler `TTS_VOICE` dans `.env`.

## Développement

Une branche par brique, une PR vers `main`, merge quand la CI est verte.

```
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # mise en forme
```
