# Architecture de Jarvis

## Principe

Le code est découpé en **couches**. Chaque couche ne connaît que celles du dessous :

```
        ui/            ← comment on affiche (fenêtre Qt, terminal)
         │
        app/           ← chef d'orchestre : enchaîne écoute → réflexion → parole
         │
  brain/   voice/   tools/   ← briques indépendantes (LLM, audio, outils)
         │
        core/          ← config, logs
```

- `app/` **ne connaît aucune interface**. Il prévient un `AssistantListener` (voir `app/events.py`)
  de tout ce qui se passe. Une nouvelle interface implémente simplement ce contrat.
- Les briques (`brain/`, `voice/`) ne se connaissent pas entre elles : c'est `app/` qui les relie.
- Règle : **un fichier = un rôle**, idéalement moins de 200 lignes. Quand un fichier grossit, on
  le découpe.

## Arborescence

```
src/jarvis/
├── __init__.py            point d'entrée : `jarvis` (fenêtre) ou `jarvis --cli` (terminal)
├── core/
│   ├── config.py          réglages lus dans .env (Settings) + chemins (data/, logs/)
│   └── logging.py         logs console + logs/jarvis.log
├── brain/
│   ├── llm.py             Brain : discussion avec Ollama (streaming, boucle d'appel d'outils)
│   ├── events.py          ToolStarted / ToolFinished : événements émis pendant une réponse
│   ├── prompts.py         personnalité de Jarvis (prompt système)
│   └── conversation.py    mémoire de la conversation en cours
├── voice/
│   ├── recorder.py        Recorder : capture du micro → audio 16 kHz
│   ├── stt.py             WhisperSTT : voix → texte (faster-whisper)
│   ├── tts.py             PiperTTS : texte → voix (Piper)
│   ├── speaker.py         Speaker : file de phrases à dire (synthèse + lecture en parallèle)
│   ├── player.py          AudioPlayer : sortie audio ouverte en permanence (pas de grésillement)
│   ├── text.py            découpage en phrases, nettoyage avant lecture
│   ├── ptt.py             PushToTalk : touche globale maintenue pour parler
│   ├── hands_free.py      HandsFreeListener : écoute continue → phrases → texte
│   ├── vad.py             StreamingVAD (Silero) + SpeechSegmenter : découpe le flux en phrases
│   ├── wake.py            repérage de « Jarvis » en début de phrase, ordres d'arrêt, écho
│   ├── cuda.py            DLL CUDA pour Whisper sur GPU (Windows)
│   ├── audition.py        outil : écouter les voix disponibles
│   └── diagnostic.py      outil : chercher l'origine de grésillements (voix sous charge)
├── app/
│   ├── assistant.py       Assistant : chef d'orchestre (thread de travail, états)
│   ├── reply.py           Reply : déroulé d'une réponse (texte, voix, outils, pop-ups)
│   ├── voice_inputs.py    VoiceInputs : push-to-talk + mains libres
│   ├── wake_control.py    WakeControl : règles du mot d'activation (réveil, relance, stop, écho)
│   ├── components.py      chargement des modèles (chacun peut échouer sans tout bloquer)
│   └── events.py          AssistantState + contrat AssistantListener
├── tools/                 outils que le LLM peut appeler (plugins)
│   ├── __init__.py        default_toolbox() : liste des outils actifs
│   ├── base.py            Tool, ToolBox, ToolResult, Display (contenu à afficher), retry()
│   ├── web_search.py      recherche internet (DuckDuckGo)
│   ├── web_page.py        lecture d'une page (trafilatura)
│   └── images.py          recherche et téléchargement d'images
└── ui/
    ├── terminal.py        interface terminal
    └── desktop/           interface de bureau (PySide6)
        ├── app.py         lancement de l'application Qt
        ├── main_window.py fenêtre principale (assemble les widgets)
        ├── bridge.py      QtBridge : événements de l'assistant → signaux Qt (thread-safe)
        ├── theme.py       couleurs et feuille de style (thème HUD)
        ├── popups/
        │   ├── manager.py     PopupManager : ouvre les pop-ups à côté de la fenêtre (3 max)
        │   ├── base.py        Popup : fenêtre sans bordure, déplaçable, en fondu
        │   ├── results.py     résultats de recherche (liens cliquables)
        │   ├── article.py     texte d'une page web
        │   └── images.py      galerie d'images
        └── widgets/
            ├── orb.py         cercle HUD animé (état + niveau de voix)
            ├── chat.py        fil de discussion en bulles
            └── input_bar.py   saisie, micro, voix, nouvelle conversation
```

## Le parcours d'un message vocal

1. `PushToTalk` détecte l'appui sur la touche → `Assistant.start_listening()`
   → `Recorder.start()`, état **LISTENING**
2. Relâchement → `Assistant.stop_listening()` → l'audio est déposé dans la file de l'assistant
3. Le thread de l'assistant : `WhisperSTT.transcribe()` → `Brain.reply()` (streaming)
4. Si le LLM demande un outil : `Brain` l'exécute via `ToolBox` (événements `ToolStarted` /
   `ToolFinished`), lui renvoie le résultat, et le LLM formule sa réponse (3 allers-retours max).
   `Reply` affiche « 🔎 Recherche… » (`on_tool`), dit une phrase d'attente et ouvre le pop-up
   (`on_display`)
5. Chaque morceau de texte part vers l'interface (`on_reply_chunk`) et vers `SentenceSplitter`
6. Chaque phrase complète part dans `Speaker` → Piper → haut-parleurs, état **SPEAKING**
7. Fin → état **IDLE**

## Le parcours d'une demande en mains libres

1. `HandsFreeListener` reçoit le micro en continu (blocs de 20 ms, convertis en 16 kHz)
2. `SpeechSegmenter` + `StreamingVAD` repèrent une phrase : début de voix → 700 ms de silence
3. Le thread `hands-free` la transcrit (`WhisperSTT`, avec `hotwords="Jarvis"`)
4. `WakeControl.on_heard()` applique les règles :
   - commence par « Jarvis » → coupe Jarvis s'il parle, puis `Assistant.submit_heard()`
   - « Jarvis » seul → « Oui, Monsieur ? » et la phrase suivante est acceptée sans le nom
   - juste après une réponse → relance possible sans le nom pendant `FOLLOW_UP_SECONDS`
   - pendant qu'il parle → un ordre court (« stop », « tais-toi ») suffit
   - ce qui ressemble à ce que Jarvis vient de dire → ignoré (écho de ses haut-parleurs)
   - le reste → ignoré (conversation autour de l'ordinateur)

## Threads

| Thread | Rôle |
|---|---|
| principal | interface (Qt ou saisie clavier du terminal) |
| `assistant` | transcription, LLM, enchaînement (une demande à la fois) |
| `tts-synth` / `tts-play` | synthèse de la phrase suivante pendant la lecture de la précédente |
| hook clavier / micro | push-to-talk et capture audio (rapides, ne font que déposer des événements) |
| `hands-free` | transcription des phrases entendues en continu + règles de réveil |
| `tool-<nom>` | un outil en cours ; abandonné après 15 s ou si l'utilisateur interrompt |

L'interface Qt ne doit jamais être modifiée depuis un autre thread : `QtBridge` convertit les
événements de l'assistant en signaux Qt, délivrés dans le thread principal.

## Ajouter…

- **un outil** : une classe `Tool` dans `tools/` (nom, description lue par le LLM, paramètres,
  `run()` qui renvoie un `ToolResult`), inscrite dans `default_toolbox()`. Pour afficher quelque
  chose, renvoyer un `Display` ; si c'est un nouveau type, ajouter un pop-up dans
  `ui/desktop/popups/` et l'inscrire dans `POPUPS` (`manager.py`)
- **un réglage** : champ dans `Settings` + lecture dans `load_settings()` (`core/config.py`)
  + ligne commentée dans `.env.example`
- **une interface** : une classe qui implémente `AssistantListener` et appelle les méthodes
  publiques d'`Assistant` (`submit_text`, `start_listening`, `interrupt`…)
- **un widget** : un fichier dans `ui/desktop/widgets/`, assemblé dans `main_window.py`
- **des couleurs** : uniquement dans `ui/desktop/theme.py`
