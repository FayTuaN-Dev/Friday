# Friday

Assistante personnelle vocale de bureau, 100 % locale par défaut : on lui parle, elle répond à voix
haute et affiche le chat, des images et des résultats dans des pop-ups. Inspirée de F.R.I.D.A.Y.,
l'IA de Tony Stark (le projet s'appelait d'abord Jarvis).

<p align="center"><img src="docs/images/interface.png" width="360" alt="Interface de Friday"></p>

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
ollama pull qwen3-vl:4b-instruct   # vision (voir l'écran)
uv sync
copy .env.example .env
```

### Agenda et mails Google (facultatif, gratuit, une seule fois)

1. Sur https://console.cloud.google.com/, créer un projet « Friday ».
2. *API et services → Bibliothèque* : activer **Google Calendar API** et **Gmail API**.
3. *Google Auth Platform* (écran de consentement) : type **Externe**, puis dans *Audience* ajouter
   son adresse Gmail comme utilisateur test, et **publier l'application** (sinon Google redemande
   la connexion tous les 7 jours ; l'avertissement « application non validée » est normal :
   *Paramètres avancés → Accéder à Friday*).
4. *Clients → Créer un client* de type **Application de bureau**, télécharger le JSON et
   l'enregistrer sous `data/google_credentials.json`.

Au lancement suivant, le navigateur s'ouvre pour autoriser Friday ; la clé est gardée dans
`data/google_token.json`. Autorisations demandées : agenda (lecture et écriture), mails (lecture
et envoi ; jamais de suppression).

## Utilisation

```
uv run friday          # application de bureau
uv run friday --cli    # version terminal
```

- **Mains libres** : dire « **Friday** » (à l'anglaise), « quelle heure est-il ? » d'une traite. « Friday » seul → il répond « Oui ? » et écoute la suite. Juste après une réponse, on peut relancer sans redire son nom. Pendant qu'il parle : « Friday, … » lui coupe la parole, « stop » le fait taire.
- **Mémoire** : il retient seul ce qui compte (« 🧠 Mémorisé : … »). « Retiens que… », « Oublie que… », « Qu'est-ce que tu sais sur moi ? »
- **Rappels et listes** : « minuteur de 10 minutes », « rappelle-moi d'appeler maman demain à 18 h », « ajoute du lait à ma liste de courses », « qu'y a-t-il sur ma liste ? ». À l'heure dite : carillon puis annonce vocale.
- **PC** : « ouvre Spotify », « ferme Discord » (avec confirmation), « ouvre YouTube », « mets le volume à 30 », « coupe le son », « musique suivante », « mets du jazz ».
- **Claude Code** : « Friday, demande à Claude d'écrire… » → il demande confirmation (« oui », ou bouton), Claude travaille en arrière-plan dans `CLAUDE_WORKSPACE`, et Friday prévient quand c'est fini. Utilise le CLI `claude` connecté au compte Pro, sans clé API.
- **Fichiers et presse-papier** : glisser un PDF, un document Word ou un fichier texte dans la fenêtre, puis « résume-le », « quelle est la date limite ? ». « Corrige ce que j'ai copié et remets-le dans le presse-papier », « traduis en anglais ce que j'ai copié », « explique le code que j'ai copié ». **Retrouver un fichier** dans Documents, Bureau, Téléchargements et Images : « trouve mon devis de mars », « où est ma photo de vacances ? », « cherche le document où je parle du carrelage », puis « ouvre-le » ou « résume-le ».
- **Voir l'écran** : « regarde mon écran », « c'est quoi cette erreur ? », « pourquoi mon code plante ? », « résume l'article que j'ai à l'écran ». Lu par un petit modèle de vision local (`ollama pull qwen3-vl:4b-instruct`) : la capture ne quitte pas le PC. Compter ~15 s (les deux modèles se relaient sur la carte graphique). En secours : « demande à Claude de regarder mon écran » (avec confirmation, la capture part alors en ligne).
- **Briefing du matin** : au premier démarrage de Friday le matin (5 h – 12 h), une fois par jour, elle présente les rubriques choisies ; une rubrique vide est passée sous silence, et si tout est vide elle ne dit rien. À la voix : « mon briefing », « ajoute la météo de Bordeaux / l'actualité tech / ma liste de tâches / une citation à mon briefing », « retire… », « qu'y a-t-il dans mon briefing ? », « désactive le briefing ». Réglages dans `data/briefing.json`.
- **Agenda et mails Google** : « qu'est-ce que j'ai demain / cette semaine ? », « ajoute dentiste jeudi à 14 h », « déplace / supprime mon rendez-vous de jeudi » (avec confirmation), « ai-je de nouveaux mails ? », « lis-moi le mail de Julie », « réponds-lui que c'est d'accord » (brouillon montré, envoi seulement après « oui »). Rubriques « agenda » et « mails » possibles dans le briefing.
- **Push-to-talk** : maintenir la touche `Début` (réglable via `PTT_KEY`), parler, relâcher.
- **Écrire** : taper son message puis Entrée.

Dans la fenêtre, les boutons de la barre du bas permettent d'envoyer, de parler (maintenir 🎙), de couper la voix et de démarrer une nouvelle conversation. En mode terminal : `/voix` (activer/couper la voix), `/reset` (nouvelle conversation), `/quit` (quitter).

Choisir le micro : `uv run python -m sounddevice` liste les périphériques, puis régler `MIC_DEVICE` (numéro ou morceau du nom).

Choisir la sortie audio : `OUTPUT_DEVICE` (même principe). En cas de grésillements : `uv run python -m friday.voice.diagnostic`.

Pour comparer les voix disponibles : `uv run python -m friday.voice.audition`, puis régler `TTS_VOICE` dans `.env`.

## Développement

Une branche par brique, une PR vers `main`, merge quand la CI est verte.

```
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # mise en forme
```
