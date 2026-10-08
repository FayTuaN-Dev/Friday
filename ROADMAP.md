# 🤖 Friday — Roadmap

Assistant personnel vocal de bureau : on lui parle, il répond à voix haute et affiche le chat, des images et des résultats dans des pop-ups.

## Choix techniques

| Brique | Choix | Remarque |
|---|---|---|
| Langage | Python 3.12 (via `uv`) | 3.12 plutôt que 3.14 : meilleure compatibilité des libs audio/IA |
| Cerveau | Ollama `qwen3:8b` (local) | Supporte l'appel d'outils |
| Tâches complexes / code | Claude Code (`sonnet`, modèle configurable) | Délégué par Friday comme un outil |
| Transcription (STT) | `faster-whisper` large-v3-turbo (local, GPU) | ~0,5 s par phrase ; `small` en secours si la VRAM manque |
| Voix (TTS) | Piper `fr_FR-siwis-medium` (local) | Option cloud plus tard si besoin |
| Interface | PySide6 (Qt) | |
| Matériel | RTX 3070 (8 Go VRAM) | qwen3:8b ≈ 5,2 Go : il reste ~2,5 Go pour Whisper |

**Principe :** tout en local par défaut, avec le cloud uniquement pour les tâches confiées à Claude Code.

---

## Fonctionnalités

### 1. 🎙️ Écouter
- [x] Push-to-talk (touche maintenue, configurable)
- [x] Détection de fin de parole (VAD — Silero, en continu)
- [x] Transcription (`faster-whisper` large-v3-turbo sur GPU)
- [x] Mot d'activation « Friday » (repéré par Whisper : « Friday, … » d'une traite)
- [x] Interruption pendant qu'il parle (« Friday, … » ou « stop »)

### 2. 🧠 Réfléchir
- [x] Discussion avec Ollama (réponse en streaming)
- [x] Personnalité Friday (prompt système)
- [x] Mémoire de la conversation en cours
- [x] Mémoire long terme (SQLite + embeddings embeddinggemma, mémorisation automatique)
- [x] Appel d'outils (tool calling)
- [x] Délégation à Claude Code (CLI `claude`, compte Pro, en arrière-plan, avec confirmation)

### 3. 🔊 Parler
- [x] Synthèse vocale Piper
- [x] Lecture phrase par phrase (latence réduite)
- [ ] Voix synchronisée avec le texte du chat

### 4. 🖥️ Application de bureau
- [x] Fenêtre de chat (historique, streaming, saisie clavier)
- [x] Indicateur d'état (veille / écoute / réfléchit / parle) avec animation audio
- [x] Pop-ups de contenu : images, articles, résultats (code : plus tard)
- [x] Refonte : fenêtre sans bordure arrondie, bulles douces, saisie en pilule, icônes fines
- [x] Noyau holographique animé (anneaux 3D, circuits, étincelles) à la place du cercle
- [x] Couleur au choix (palettes ou couleur libre), toute l'interface s'accorde, mémorisée
- [ ] Icône dans la zone de notification
- [ ] Raccourci clavier global
- [x] Écran de réglages (apparence, voix, écoute, briefing, fonctions, compte Google), écrit dans le .env

### 5. 🛠️ Outils
**Information**
- [x] Recherche web + résumé
- [x] Lecture/résumé d'une page web
- [x] Recherche d'images → pop-up
- [x] Météo (Open-Meteo, gratuit et sans clé) ; actualités via la recherche web ; date/heure dans le prompt

**Productivité**
- [x] Minuteurs et rappels (carillon + annonce vocale, rattrapage des rappels manqués)
- [x] Notes et listes (courses, tâches…)
- [x] Agenda et mails (Google) : lire, ajouter, déplacer / supprimer (confirmé), mails lus et envoyés (confirmé)
- [x] Calculs et conversions (le LLM s'en charge directement)

**Contrôle du PC**
- [x] Ouvrir/fermer applications (menu Démarrer, fermeture avec confirmation) et sites
- [x] Volume, musique (touches multimédia, recherche Spotify)
- [x] Lecture/résumé de fichiers (PDF, Word, texte ; glisser-déposer dans la fenêtre)
- [x] Recherche de fichiers (Documents, Bureau, Téléchargements, Images), par nom ou contenu, et ouverture
- [x] Presse-papier (lire ce qui est copié, y remettre un texte corrigé ou traduit)
- [x] Capture d'écran + analyse (vision locale qwen3-vl, Claude en secours)

**Bonus (plus tard)**
- [ ] Domotique (Home Assistant)
- [ ] Webcam / vision
- [x] Briefing du matin à rubriques choisies (météo, rappels, listes, actualités, rubrique libre)

### 6. ⚙️ Fondations
- [x] Architecture modulaire (outils = plugins), voir docs/ARCHITECTURE.md
- [x] Config `.env` + fichier de réglages
- [x] Logs (gestion d'erreurs : au fil des phases)
- [x] Confirmation avant les actions sensibles (voix, clavier ou bouton)
- [x] Aiguillage des outils par compétence (12 outils au lieu de 43, prompt ÷3) + `load_skill`
- [x] Garde-fous contre l'injection (contenu externe encadré, actions confirmées après lecture)
- [x] Réflexion à la demande (« réfléchis ») et automatique pour les calculs ; formules dites en mots
- [ ] Démarrage avec Windows + `.exe` (PyInstaller)

---

## Notes pour plus tard

- **Recherche web plus fiable** : les moteurs gratuits (via `ddgs`) limitent parfois les requêtes
  d'une même connexion. Si ça devient gênant, ajouter un fournisseur avec clé gratuite en secours :
  Brave Search API (2 000 recherches/mois) ou Tavily (1 000/mois, pensé pour les assistants IA).
  Choix actuel : s'en passer tant que possible.
- **Lancer directement une playlist Spotify** (« mets le mix Nova ») : impossible sans l'API
  Spotify (application développeur gratuite + connexion au compte). Aujourd'hui Friday ouvre la
  recherche et il faut cliquer sur le résultat.
- **Friday hors du PC** (bot Telegram…) : demanderait que le PC reste allumé en permanence, ce
  qui n'est pas le cas. Projet futur.
- **Meilleure voix** : Kokoro (local) ou Edge TTS (gratuit, en ligne) à essayer ; pas d'API payante.

---

## Plan d'action

| # | Phase | Livrable | Statut |
|---|---|---|---|
| 0 | Mise en place : `uv`, Python 3.12, git, structure, `.env` | Projet prêt | ✅ |
| 1 | Cerveau texte : chat Ollama en terminal, historique, personnalité | On lui parle au clavier | ✅ |
| 2 | Voix de sortie : Piper, phrase par phrase | Il répond à voix haute | ✅ |
| 3 | Voix d'entrée : push-to-talk + Whisper | 1re conversation 100 % vocale | ✅ |
| 4 | Interface : fenêtre chat + indicateur d'état | Friday a un visage | ✅ |
| 5 | Premiers outils : recherche web + pop-ups images/textes | Il cherche et montre | ✅ |
| 6 | Mains libres : mot d'activation + interruption | Expérience naturelle | ✅ |
| 7 | Mémoire long terme | Il se souvient de toi | ✅ |
| 8 | Outils perso + délégation Claude Code | Assistant du quotidien | ✅ |
| 9 | Finitions : tray, démarrage auto, `.exe` | Produit fini | ⬜ (reporté) |

### Friday v2

Choisies en tenant compte du PC (qwen3:8b sur RTX 3070 8 Go) : rien de trop lourd, pas d'API payante.

| # | Brique | Livrable | Statut |
|---|---|---|---|
| A | Refonte de l'interface + noyau holographique + couleur au choix | Friday a un nouveau visage | ✅ |
| B | Comprendre ce qui m'entoure : presse-papier et lecture de fichiers, recherche dans les fichiers, voir l'écran | Friday voit ce que je vois | ✅ |
| C | Briefing du matin, avec des rubriques choisies (en ajouter, en retirer) | « Bonjour Friday » | ✅ |
| D | Agenda et mails Google | Friday gère mon planning | ✅ |
| E | Longues conversations : carnet de recherche, résumé glissant, mémoire de travail doublée (16 k) | Friday tient une longue recherche | ✅ |
| F | Bibliothèque de documents (RAG local) | « Que dit mon livre sur… » | ✅ |
| G | Mode trading : analyses par Claude isolé après aperçu, calculs de risque, journal local (écran + courbe en R), capture ciblée du graphique TradingView | Friday m'accompagne en trading | ✅ |
| H | Données pour les analyses : marché (bougies, indicateurs), cours ; calendrier économique, actualités, COT, séances ; annonces du jour + résultats publiés (FRED) + heures de trading ; bibliothèque de trading légale | Des analyses mieux informées, tout instrument | ✅ |

### Prochaines étapes — trading

À attaquer une par une (une PR chacune), dans cet ordre :

| # | Brique | Livrable | Statut |
|---|---|---|---|
| T1 | **Check-list avant trade** : les règles du plan vérifiées par le code (tendance / MM200, zone RSI, annonce forte dans les 30 min, risque ≤ 1 %, R/R ≥ 2) | « Je veux acheter l'or à 4 160, stop 4 140 » → feu vert / rouge, règle par règle, sans Claude | ✅ |
| T2 | **Backtest du plan** sur l'historique (Yahoo : 2 ans en 1 h, plus en journalier) | Nombre de trades, % gagnants, espérance en R, pire série ; comparer des variantes du plan | ✅ |
| T3 | **Alertes** : niveaux et conditions du plan surveillés en local, annoncés à la voix | « L'or touche la MM50 4 h avec RSI 44 : ton setup se forme » | ✅ |
| T4 | **Journal qui apprend** : setup utilisé, plan respecté ?, capture d'entrée, état d'esprit ; statistiques par setup / instrument / heure ; revue hebdomadaire (bilan anonyme) par Claude | Savoir ce qui marche et ce qui coûte | ✅ |
| T5 | **Briefing trading à 9 h** (rubrique du briefing) : annonces du jour, mouvement de la nuit, niveaux clés, règles du plan | Début de journée de trading préparé | ✅ |
| T6 | **Analyses plus rapides et mieux nourries** : données préparées en avance en mode trading (aperçu instantané), mémoire des analyses de Claude (et plus tard leur comparaison avec ce que le marché a fait), recherche dans la bibliothèque enrichie (instrument + sujet), données européennes (BCE : inflation, chômage, sans clé) | Moins d'attente, moins de quota, de meilleures sources | ✅ |
| T7 | **Bibliothèque de stratégies** : d'autres familles que le plan actuel (cassure de range, croisement de moyennes, retour à la moyenne, cassure d'ouverture de séance…), chacune backtestée sur chaque instrument et comparée aux autres avec sa marge d'incertitude ; on ne garde que celles qui ont fonctionné sur le passé, et la stratégie choisie devient celle de la check-list et des alertes | Trader une stratégie qui a marché sur l'historique, pas une intuition | ✅ |
| T7b | **Ton plan écrit devient la stratégie** : traduit en règles par Claude (après aperçu), vérifiées et redites en français par le code ; backtest, comparaison, alertes, check-list et briefing l'utilisent ; « Ma stratégie » dans les réglages (plan écrit ou stratégie de base) | Trader et tester SA stratégie, écrite librement | ✅ |
| T7c | **Carnet de plans écrits** : autant de stratégies écrites que voulu (nommer, dupliquer, supprimer), chacune traduite, testée (« teste le plan … »), comparée aux autres et choisie ; le plan suivi est celui joint aux analyses | Écrire et tester plein de stratégies, une à une ou toutes ensemble | ✅ |

### Prochaines étapes — Friday

| # | Brique | Livrable | Statut |
|---|---|---|---|
| F1 | **Fiabilité** : surveillance d'Ollama (vitesse effondrée → rechargement du modèle tout seul, constaté une fois), sauvegarde automatique de `data/` (mémoire, journal, notes, bibliothèque), page « Diagnostic » (Ollama, carte graphique, modèles, micro) | Friday ne se dégrade plus en silence, rien ne se perd | ✅ |
| F2 | **Mot d'activation dédié** : openWakeWord abandonné (l'entraînement d'un modèle « Friday » ne fonctionne plus sur Colab en 2026) ; piste restante : un petit Whisper sur le processeur réservé au repérage de « Friday », le gros seulement pour la demande | Moins de faux déclenchements, moins de calcul | ⏸️ (abandonné, alternative à étudier) |
| F3 | **Notifications Windows** quand une tâche de fond finit (Claude, analyse, rappel) même fenêtre réduite | Rien ne passe inaperçu | ✅ |
| F4 | **Mails** : la vraie liste des catégories donnée au modèle (« quelles catégories ai-je ? » ne marchait que 5 fois sur 8) | Tri des mails fiable | ⬜ |
| F5 | **Mémoire de la journée** : résumé des conversations du jour gardé (« de quoi on a parlé hier ? ») | Continuité d'un jour à l'autre | ⬜ |
| F6 | **Friday sur le téléphone** (à étudier : accès privé depuis le réseau local, sans service payant) | Parler à Friday hors du bureau | ⬜ |
| F7 | **Limites Claude à l'écran** : fenêtre agrandie, une barre pour ce qu'il reste de la session (5 h) et de la semaine, avec la remise à zéro ; chiffres relayés par la ligne d'état de Claude Code | Savoir d'un coup d'œil ce qu'il reste avant d'envoyer une analyse | ✅ |
| 9 | Finitions : icône près de l'horloge, démarrage avec Windows, `.exe` | Produit fini | ⬜ (reporté) |

