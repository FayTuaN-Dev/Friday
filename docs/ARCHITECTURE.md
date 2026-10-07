# Architecture de Friday

## Principe

Le code est découpé en **couches**. Chaque couche ne connaît que celles du dessous :

```
        ui/            ← comment on affiche (fenêtre Qt, terminal)
         │
        app/           ← chef d'orchestre : enchaîne écoute → réflexion → parole
         │
  brain/  voice/  memory/  tools/   ← briques indépendantes (LLM, audio, mémoire, outils)
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
src/friday/
├── __init__.py            point d'entrée : `friday` (fenêtre) ou `friday --cli` (terminal)
├── core/
│   ├── env_file.py        lire / modifier le .env en gardant ses commentaires (écran de réglages)
│   ├── settings_schema.py réglages de l'écran : clé, libellé, type, aide (une ligne = un réglage)
│   ├── config.py          réglages lus dans .env (Settings) + chemins (data/, logs/)
│   └── logging.py         logs console + logs/friday.log
├── brain/
│   ├── llm.py             Brain : discussion avec Ollama (streaming, boucle d'appel d'outils)
│   ├── events.py          ToolStarted / ToolFinished : événements émis pendant une réponse
│   ├── prompts.py         personnalité de Friday (prompt système)
│   ├── skills.py          compétences : outils + consignes + mots-clés + exemples par domaine
│   ├── router.py          SkillRouter : quelles compétences pour cette demande (mots-clés, sens)
│   ├── toolset.py         Toolset : outils et consignes donnés au modèle, load_skill (secours) ;
│   │                      une compétence reste active tant que le sujet continue (3 échanges)
│   ├── second_chance.py   relance unique : réponse vide (outil non proposé) ou « je note » sans outil
│   ├── summary.py         résumé glissant : vieux échanges résumés quand la mémoire de travail se remplit
│   ├── safety.py          contenu externe encadré ; confirmation des actions qui suivent sa lecture
│   ├── thinking.py        réflexion à la demande (« réfléchis ») ou pour les calculs
│   └── conversation.py    mémoire de la conversation en cours (+ résumé du début)
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
│   ├── wake.py            repérage de « Friday » en début de phrase, ordres d'arrêt, écho
│   ├── cuda.py            DLL CUDA pour Whisper sur GPU (Windows)
│   ├── audition.py        outil : écouter les voix disponibles
│   ├── diagnostic.py      outil : chercher l'origine de grésillements (voix sous charge)
│   └── sounds.py          sons synthétisés (carillon des rappels)
├── memory/                mémoire long terme (data/memory.db)
│   ├── store.py           MemoryStore : souvenirs dans SQLite (texte + vecteur de sens)
│   ├── embedder.py        Embedder : texte → vecteur (embeddinggemma via Ollama, sur CPU)
│   ├── service.py         MemoryService : retenir (sans doublon), oublier, souvenirs utiles
│   └── extractor.py       FactExtractor : le LLM tire les faits durables d'une phrase (JSON)
├── agenda/                rappels et notes (data/agenda.db)
│   ├── store.py           AgendaStore : rappels et listes dans SQLite
│   ├── times.py           calcul des dates (« 18:00 » + « demain » → date exacte)
│   └── scheduler.py       ReminderScheduler : déclenche à l'heure, rattrape les manqués
├── trading/               mode trading (« mode trading » / « fin du mode trading »)
│   ├── mode.py            état du mode, commandes, aiguillage local / analyse (déterministe)
│   ├── masking.py         masquage avant aperçu : montants, comptes, IBAN, e-mails, clés, chemins
│   ├── context_builder.py paquet minimal (question + extraits plafonnés), balises neutralisées ;
│   │                      `approved` ne passe à True que par la confirmation de l'utilisateur
│   ├── analyst.py         Claude ISOLÉ : --restricted, --tools "" (« Read » seulement avec une
│   │                      capture, confiné à son dossier), sans MCP ni session gardée
│   ├── capture.py         capture CIBLÉE : la seule fenêtre TradingView (PrintWindow : rien de ce
│   │                      qui la recouvre), recadrée sur la zone de data/trading.json ; sinon rien
│   ├── instruments.py     fiches : forex, or, argent, pétrole, indices, crypto, actions (symbole
│   │                      Yahoo, pip/point, lot, devises) ; détection dans la phrase ou le titre
│   ├── market.py          bougies OHLC (Yahoo) + indicateurs calculés sur le PC (MM, RSI, ATR, pivots)
│   ├── reference_rates.py cours de référence officiels de la BCE (Frankfurter)
│   ├── calendar.py        annonces économiques (ForexFactory) des devises de l'instrument
│   ├── news.py            actualités des dernières 24 h (FXStreet), filtrées par instrument
│   ├── cot.py             positionnement des grands spéculateurs (rapport COT de la CFTC)
│   ├── sessions.py        heure et séances ouvertes (Sydney, Tokyo, Londres, New York)
│   ├── related.py         marchés liés : dollar (DXY), taux US 10 ans, VIX, S&P 500, or/argent
│   ├── context_sources.py assemble ces blocs + le plan de trading ; une source en panne
│   │                      n'empêche pas les autres
│   ├── cache.py           cache disque (data/cache) : sources gratuites ménagées, secours
│   ├── risk_calc.py       valeur du pip/point, taille de position, R/R, R — tout instrument
│   └── journal.py         data/trading.db : trades + trace de chaque envoi (empreinte des images)
├── library/               bibliothèque de documents (data/bibliotheque → data/library.db)
│   ├── chunker.py         découpe en passages (~900 caractères, chevauchement, n° de page)
│   ├── store.py           SQLite : documents, passages, vecteurs + index plein texte FTS5
│   ├── library.py         Library : synchronise le dossier, recherche hybride (sens + mots, RRF)
│   └── catalog.py         bibliothèque de trading de départ : documents légaux seulement
│                          (Wikipédia CC BY-SA, AMF, Banque de France, Fed, BRI), source citée
├── files/                 fichiers et presse-papier (sans dépendre des outils)
│   ├── readers.py         read_document : texte d'un PDF (pypdf), Word (python-docx), texte
│   ├── clipboard.py       presse-papier Windows (ctypes) : texte ou fichiers copiés
│   ├── folders.py         dossiers autorisés (Documents, Bureau, Téléchargements, Images)
│   ├── search.py          FileFinder : recherche par nom (fautes tolérées, mois/année = date)
│   ├── content_search.py  recherche de mots dans les documents (limitée dans le temps)
│   └── opener.py          ouvrir un fichier / le montrer dans l'explorateur
├── briefing/              briefing du matin (data/briefing.json)
│   ├── config.py          BriefingConfig : activé, plage horaire, rubriques (voix ou réglages)
│   ├── sections.py        contenu de chaque rubrique (None = rien à dire : silence)
│   └── briefing.py        Briefing : quand le faire, collecte en parallèle, gestion des rubriques
├── google/                compte Google de l'utilisateur
│   ├── auth.py            GoogleAccount : autorisation OAuth (navigateur), clé dans data/
│   ├── days.py            « jeudi », « le 12 novembre », « cette semaine » → dates (pas le LLM)
│   ├── calendar.py        GoogleCalendar : lire, ajouter, déplacer, supprimer
│   ├── event_ref.py       retrouver l'événement visé (« le 2 », « supprime-le », « banque »)
│   ├── gmail.py           Gmail : derniers mails, recherche, lecture, envoi
│   ├── mailbox.py         étiquettes « Friday/… », corbeille (jamais d'effacement définitif)
│   ├── sorter.py          tri par catégorie : qwen3 classe, Friday étiquette
│   └── sources.py         agenda du jour et mails non lus pour le briefing
├── vision/                voir l'écran
│   ├── capture.py         capture de l'écran sous la souris (mss), réduite à 1600 px
│   └── reader.py          ScreenReader : le modèle de vision local décrit et recopie l'écran
├── app/
│   ├── assistant.py       Assistant : chef d'orchestre (thread de travail, états)
│   ├── briefing_trigger.py briefing automatique : une fois par jour, au premier démarrage du matin
│   ├── attachments.py     fichiers glissés + presse-papier joints à la demande (par Friday, pas le LLM)
│   ├── reply.py           Reply : déroulé d'une réponse (texte, voix, outils, pop-ups)
│   ├── voice_inputs.py    VoiceInputs : push-to-talk (appui/relâchement) + mains libres
│   ├── confirmations.py   ConfirmationGate : « Je lance ? » → oui / non (voix, clavier, bouton)
│   ├── memory_keeper.py   MemoryKeeper : mémorisation automatique en arrière-plan
│   ├── reminders.py       rappel échu → carillon + annonce par Friday
│   ├── wake_control.py    WakeControl : règles du mot d'activation (réveil, relance, stop, écho)
│   ├── hands_free_target.py  ce que l'écoute mains libres demande à l'assistant (« Oui ? »…)
│   ├── extras.py          chargement du compte Google et du briefing
│   ├── components.py      chargement des modèles (chacun peut échouer sans tout bloquer)
│   ├── gpu_check.py       au démarrage : le modèle tient-il entier dans la carte graphique ?
│   ├── prefetch.py        préparé d'office : bibliothèque, ou analyse de trading (en mode trading)
│   └── events.py          AssistantState + contrat AssistantListener
├── tools/                 outils que le LLM peut appeler (plugins)
│   ├── __init__.py        default_toolbox() : liste des outils actifs
│   ├── base.py            Tool, ToolBox, ToolResult, Display (contenu à afficher), retry()
│   ├── web_search.py      recherche internet (DuckDuckGo)
│   ├── web_page.py        lecture d'une page (trafilatura) : adresse ou numéro d'un résultat
│   ├── library.py         search_library, list_library, update_library
│   ├── trading.py         calculs de risque et journal (locaux, mode trading seulement)
│   ├── markets.py         market_quote : le cours d'un instrument, à la source (tous les jours)
│   ├── trading_analysis.py analyse par Claude : aperçu, refus sans validation, journal
│   ├── research.py        carnet de recherche : derniers résultats et pages lues, avec leurs adresses
│   ├── images.py          recherche et téléchargement d'images
│   ├── files.py           read_file (par parties) / read_clipboard / copy_to_clipboard
│   ├── file_search.py     search_files / open_file
│   ├── briefing.py        morning_briefing / configure_briefing
│   ├── google_calendar.py list_events / add_event / move_event, delete_event (confirmés)
│   ├── gmail.py           check_mail / search_mail / read_mail / send_mail (confirmé)
│   ├── mail_sorting.py    sort_mails (tout : en arrière-plan) / category_mails
│   ├── mail_trash.py      trash_mails : catégories, « tout sauf… », expéditeur (confirmé)
│   ├── google_tools.py    liste des outils Google ; google_base.py : erreurs Google lisibles
│   ├── popups.py          close_popups : Friday ferme ses propres pop-ups
│   ├── screen.py          look_at_screen (local) / ask_claude_about_screen (secours, confirmé)
│   ├── weather.py         météo actuelle + 7 jours (Open-Meteo, sans clé)
│   ├── claude_code.py     délégation à Claude Code (CLI `claude`, compte Pro), en arrière-plan
│   ├── pc/                contrôle du PC (Windows uniquement)
│   │   ├── apps_index.py  AppIndex : applis du menu Démarrer (Get-StartApps), recherche tolérante
│   │   ├── apps.py        open_app / close_app (fermeture propre WM_CLOSE, avec confirmation)
│   │   ├── windows.py     processus d'une appli (psutil) et fermeture de ses fenêtres
│   │   ├── media.py       set_volume (pycaw), media_control (touches multimédia), play_music
│   │   └── web.py         open_website
│   ├── weather_codes.py   codes météo WMO → texte français + icône
│   ├── memory.py          remember / forget_memory / list_memories
│   ├── reminders.py       set_timer / set_reminder / list_reminders / cancel_reminder
│   └── notes.py           add_note / list_notes / remove_note
└── ui/
    ├── terminal.py        interface terminal
    └── desktop/           interface de bureau (PySide6)
        ├── app.py         lancement de l'application Qt
        ├── main_window.py fenêtre principale sans bordure (assemble les widgets, applique la couleur)
        ├── bridge.py      QtBridge : événements de l'assistant → signaux Qt (thread-safe)
        ├── icons.py       icônes fines au trait (SVG), colorées par le thème
        ├── native_window.py coins arrondis natifs de Windows 11 (pas de clignotement)
        ├── preferences.py préférences choisies dans l'appli (couleur), data/interface.json
        ├── theme/
        │   ├── palette.py     une couleur de base → toute la palette (fond, bulles, états…)
        │   ├── stylesheet.py  feuille de style Qt générée à partir de la palette
        │   └── __init__.py    current() / apply_theme() : changement de couleur à chaud
        ├── journal/       journal de trading : window.py (bilan en R, tableau, clôture,
        │                  suppression, export CSV), trade_form.py (nouveau trade vérifié)
        ├── settings/      écran de réglages (zone_picker.py : tracer la zone du graphique)
        │   ├── window.py      SettingsWindow : menu, pages, Enregistrer / Redémarrer
        │   ├── form_page.py   page construite depuis settings_schema (interrupteurs, listes…)
        │   ├── briefing_page.py  briefing : activé, heures, rubriques (appliqué tout de suite)
        │   └── other_pages.py Apparence (couleur) et Comptes (Google)
        ├── popups/
        │   ├── manager.py     PopupManager : ouvre les pop-ups à côté de la fenêtre (3 max)
        │   ├── base.py        Popup : fenêtre sans bordure arrondie, déplaçable, en fondu
        │   ├── results.py     résultats de recherche (liens cliquables)
        │   ├── article.py     texte d'une page web
        │   ├── images.py      galerie d'images
        │   ├── memories.py    « Ce que je sais sur vous »
        │   ├── weather.py     météo du jour + 7 jours
        │   ├── claude.py      compte rendu de Claude Code + fichiers + dossier
        │   ├── files.py       fichiers trouvés (ouvrir, montrer dans le dossier)
        │   ├── screen.py      « Ce que je vois » : la capture analysée
        │   └── items.py       liste générique (rappels, notes)
        └── widgets/
            ├── holo/          noyau holographique animé (état + niveau de voix)
            │   ├── scene.py       géométrie 3D (anneaux, rayons, circuits, particules), numpy
            │   ├── layers.py      couches de dessin en lumière additive
            │   └── orb.py         HoloOrb : animation, états, voix, couleur
            ├── toggle.py      interrupteur arrondi aux couleurs du thème
            ├── frame.py       marge de redimensionnement de la fenêtre sans bordure
            ├── title_bar.py   barre de titre maison (couleur, réduire, agrandir, fermer)
            ├── color_menu.py  menu des couleurs (palettes + couleur libre)
            ├── chat.py        fil de discussion en bulles
            ├── confirm_card.py  carte « Je lance ? » [Lancer] / [Annuler]
            └── input_bar.py   saisie en pilule, micro, voix, nouvelle conversation
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
3. Le thread `hands-free` la transcrit (`WhisperSTT`, avec `hotwords="Friday"`)
4. `WakeControl.on_heard()` applique les règles :
   - si le nom manque au début, ce début est retranscrit dans la langue du nom (`WAKE_LANGUAGE`,
     « Friday » est anglais) : Whisper réglé en français saute souvent un mot anglais
   - commence par « Friday » → coupe Friday s'il parle, puis `Assistant.submit_heard()`
   - « Friday » seul → « Oui, Monsieur ? » et la phrase suivante est acceptée sans le nom
   - juste après une réponse ou un « Oui ? » → relance possible sans le nom pendant
     `FOLLOW_UP_SECONDS` (comparé au moment où la phrase **commence**, pas à sa transcription)
   - une phrase sans le nom juste après cette fenêtre → signalée (« commencez par Friday »)
   - pendant qu'il parle → un ordre court (« stop », « tais-toi ») suffit
   - ce qui ressemble à ce que Friday vient de dire → ignoré (écho de ses haut-parleurs)
   - le reste → ignoré (conversation autour de l'ordinateur)

## La mémoire

- **Rappel** : à chaque question, `Brain` demande à `MemoryService.relevant()` les souvenirs
  utiles (tous s'il y en a ≤ 40, sinon les 12 plus proches par le sens) et les met dans le
  prompt système, numérotés : `[3] L'utilisateur est allergique aux arachides.`
- **Sur demande** : « retiens que… » → outil `remember` (avec `replaces` pour une correction),
  « oublie que… » → `forget_memory` avec le numéro, « que sais-tu sur moi ? » → `list_memories`
- **Automatique** : après chaque réponse, `MemoryKeeper` (thread `memory`) fait relire la phrase
  par `FactExtractor`, qui renvoie les faits durables en JSON (souvent aucun). `MemoryService`
  évite les doublons (score ≥ 0,90) et applique les remplacements. L'interface affiche
  « 🧠 Mémorisé : … » (`on_memory`)

## Les actions sensibles et Claude Code

- Un outil marqué `needs_confirmation = True` (aujourd'hui : `ask_claude_code`) n'est jamais lancé
  directement. `Brain` émet une `ConfirmationRequest` ; `Reply` dit la question et
  `ConfirmationGate` l'affiche (carte avec boutons) ; la réponse arrive d'un autre thread (clic,
  « oui » au clavier, ou à la voix **sans redire « Friday »**). Pas de réponse en 60 s ou
  interruption : rien n'est lancé.
- `ask_claude_code` lance le CLI `claude -p … --permission-mode acceptEdits` dans
  `CLAUDE_WORKSPACE`, **en arrière-plan** (thread `claude`) : Friday reste disponible. À la fin,
  `on_background` dépose le résultat dans la file de l'assistant, qui ouvre le pop-up et
  **annonce** lui-même la fin (une réponse déclenchée par un message automatique).
  `cancel_claude_task` arrête la tâche.

## Threads

| Thread | Rôle |
|---|---|
| principal | interface (Qt ou saisie clavier du terminal) |
| `assistant` | transcription, LLM, enchaînement (une demande à la fois) |
| `tts-synth` / `tts-play` | synthèse de la phrase suivante pendant la lecture de la précédente |
| hook clavier / micro | push-to-talk et capture audio (rapides, ne font que déposer des événements) |
| `hands-free` | transcription des phrases entendues en continu + règles de réveil |
| `memory` | mémorisation automatique après chaque réponse |
| `claude` | une tâche Claude Code (plusieurs minutes possibles) |
| `reminders` | vérifie chaque seconde si un rappel est échu |
| `tool-<nom>` | un outil en cours ; abandonné après 15 s ou si l'utilisateur interrompt |

L'interface Qt ne doit jamais être modifiée depuis un autre thread : `QtBridge` convertit les
événements de l'assistant en signaux Qt, délivrés dans le thread principal.

## Ajouter…

- **une compétence** : ses outils, consignes et mots-clés dans `brain/skills.py` (un outil
  rangé dans aucune compétence est donné au modèle à chaque demande)
- **un outil** : une classe `Tool` dans `tools/` (nom, description lue par le LLM, paramètres,
  `run()` qui renvoie un `ToolResult`), inscrite dans `default_toolbox()`. Pour afficher quelque
  chose, renvoyer un `Display` ; si c'est un nouveau type, ajouter un pop-up dans
  `ui/desktop/popups/` et l'inscrire dans `POPUPS` (`manager.py`)
- **un réglage** : champ dans `Settings` + lecture dans `load_settings()` (`core/config.py`)
  + ligne commentée dans `.env.example`
- **une interface** : une classe qui implémente `AssistantListener` et appelle les méthodes
  publiques d'`Assistant` (`submit_text`, `start_listening`, `interrupt`…)
- **un widget** : un fichier dans `ui/desktop/widgets/`, assemblé dans `main_window.py`
- **des couleurs** : uniquement dans `ui/desktop/theme/`, déduites de la couleur de base
  (jamais de couleur en dur dans un widget : elle ne suivrait pas le choix de l'utilisateur)
