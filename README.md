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
- **Mode trading** (forex) : « mode trading » / « fin du mode trading » (le titre de la fenêtre l'indique). Les questions d'analyse partent à **Claude Code isolé** (aucun outil, ni fichiers du PC, ni web, ni connecteurs, conversation non gardée) avec 8 à 15 extraits de ta bibliothèque, **seulement après un aperçu** : tu vois exactement ce qui part, tu peux retirer des extraits, puis « Envoyer » ou « oui » (sans réponse, rien ne part). Montants, numéros de compte, IBAN, e-mails, clés et chemins sont masqués avant l'aperçu (plus les mots de `TRADING_BLOCKLIST`). Tous instruments : devises, or et argent, pétrole, indices, crypto, actions — on change en le nommant (« et sur l'or ? ») ou en changeant de graphique dans TradingView. Chaque analyse joint les **données de marché** de l'instrument (bougies Yahoo, indicateurs calculés sur le PC : moyennes mobiles, RSI, ATR, pivots, plus hauts / bas), décochables dans l'aperçu, ainsi que le **contexte** : annonces économiques des 48 h (ForexFactory), actualités des 24 h (FXStreet), positionnement des grands spéculateurs (rapport COT), séances ouvertes, et **ton plan de trading** (*Réglages → Trading*, masqué comme tes questions) ; Claude répond en scénarios (haussier, baissier, chacun avec son niveau d'invalidation), annonces à surveiller et risques, et juge l'idée au regard de ton plan. Sources gratuites mises en cache (data/cache) ; si l'une ne répond pas, l'aperçu le dit et le reste part. Calculs (valeur du pip ou du point, taille de position, risque/rendement) faits par du code sur le PC, cours manquants récupérés d'office (Yahoo, cours de référence BCE), journal de trading local (`data/trading.db`, avec la trace de chaque envoi). Si la question parle du graphique (« regarde mon graphique », « ces bougies »…), Friday joint une **capture de la seule fenêtre TradingView** (même recouverte par une autre fenêtre, rien d'autre n'apparaît), recadrée sur la zone tracée dans *Réglages → Trading → Choisir la zone…* (laisse dehors solde et positions : une image ne peut pas être masquée automatiquement) ; elle est montrée dans l'aperçu, peut être décochée, n'est lisible par Claude que dans son dossier, puis supprimée (seule son empreinte reste au journal). Jamais de capture de l'écran entier, ni en continu. Claude explique et challenge, cite les sources, signale les risques ; jamais d'ordre, aucune connexion à un courtier. **Check-list avant trade** (« je veux acheter l'or à 4 160, stop 4 140 », « ce trade respecte mon plan ? ») : les règles chiffrées de ton plan (*Réglages → Trading → Règles vérifiées par le code* : tendance par l'EMA200 journalière, repli sur l'EMA50 1 h, zone du RSI, stop d'au moins 1,5 ATR, objectif d'au moins 2 R, risque d'au plus 1 %, trades ouverts, pas d'annonce forte dans les 30 min ; chaque règle se désactive à 0) sont vérifiées **par le code, sans Claude** : feu vert, orange (donnée manquante : objectif, capital…, avec le niveau à viser) ou rouge, règle par règle à l'écran. Ce n'est jamais un signal, seulement le respect de ton plan. Pour avoir l'avis de Claude sur une idée chiffrée, demande-le explicitement (« analyse mon achat de l'or à 4 108, stop 4 060 »). **Backtest du plan** (« teste mon plan sur l'or », « et avec un objectif à 3 R ? ») : ces mêmes règles rejouées sur environ deux ans et demi de bougies 1 h (Yahoo), sur le PC : nombre de trades, % gagnants, gain moyen en R (avec sa marge d'incertitude), pire série de pertes, plus forte baisse, et la comparaison avec des variantes qui ne changent qu'une règle (sans filtre de tendance, objectif 1,5 ou 3 R, stop 1 ou 2 ATR…). Une variante n'est dite meilleure que si l'écart dépasse la marge du hasard. Entrée à la clôture 1 h, stop compté si stop et objectif sont touchés dans la même bougie, spread typique déduit ; les annonces ne sont pas rejouées. Le passé ne garantit rien. **Alertes** (« préviens-moi si l'or passe 4 150 », « surveille l'or », « mes alertes », « annule l'alerte 2 ») : surveillées sur le PC tant que Friday tourne, annoncées avec le carillon puis à la voix. Une alerte de prix sonne une fois, à toute heure. Surveiller un instrument annonce le **setup de ton plan** quand il apparaît, à la clôture d'une bougie 1 h et pendant tes heures de trading : les mêmes règles que le backtest, avec un stop et un objectif indicatifs. Les niveaux suivent le cours de ton graphique TradingView (pour l'or, l'écart avec le contrat à terme de Yahoo est retenu). Les alertes sont gardées dans `data/trading_alerts.json`. **Briefing trading** : en semaine, au début de tes heures de trading (ou au démarrage de Friday pendant celles-ci), une fois par jour, Friday lit avec le carillon les annonces fortes du jour (noms en français), le mouvement de la nuit depuis la veille 18 h, les niveaux clés (plus haut et plus bas d'hier, pivots, EMA50 1 h), la tendance et donc le sens que ton plan autorise aujourd'hui, et le rappel de tes règles. À la voix, en mode trading : « briefing trading », « prépare ma journée de trading », « briefing trading sur l'argent ». Instruments : *Réglages → Trading → Instruments du briefing trading* (vide : ceux que tu surveilles). Tout est calculé sur le PC. **Analyses plus rapides et mieux nourries** : en mode trading, les données publiques (marché, marchés liés, actualités) sont préparées en avance pour l'instrument courant et ceux que tu surveilles, donc l'aperçu s'ouvre aussitôt. Claude reçoit aussi **ses analyses précédentes** sur le même instrument, avec ce que le cours a fait depuis (décochables dans l'aperçu), pour dire ce qui s'est confirmé. La bibliothèque est cherchée sur le sujet de ta question, puis sur l'instrument lui-même. Pour un instrument en euro, Friday joint les **chiffres officiels de la zone euro** (inflation Eurostat, chômage et taux de dépôt BCE, gratuits et sans clé). « Mes dernières analyses » : les analyses de Claude et le cours depuis. **Bibliothèque de stratégies** : « compare les stratégies sur l'or » (ou « sur tous mes instruments ») backteste avec le même moteur, le même spread et la même gestion du risque ton plan, le croisement de moyennes, la cassure de range, le retour à la moyenne et la cassure de l'ouverture de Londres. Chacune reçoit un verdict honnête : ✅ **a fonctionné** (au moins 30 trades, gain positif même marge d'incertitude retirée, et positif sur chacune des deux moitiés de la période), 🟡 **prometteuse** (positive mais pas prouvée), ❌ **n'a pas fonctionné**. « Choisis la cassure de l'ouverture de Londres pour l'or » : elle devient la stratégie des alertes, de la check-list (son signal récent remplace les règles d'entrée du plan) et du briefing pour cet instrument. Une stratégie qui n'a pas fonctionné est refusée ; « reviens à mon plan » est toujours possible. **Tes plans écrits sont tes stratégies** : dans *Réglages → Trading → Mes plans de trading*, écris-en autant que tu veux, chacun avec un nom (« Cassure Londres », « Repli EMA strict »… ; *Nouveau*, *Dupliquer* pour tester une variante, *Supprimer*). « **Traduire en règles** » (ou « traduis le plan Cassure Londres » en mode trading) : Claude, après l'aperçu habituel, le traduit en règles précises (indicateurs, conditions d'achat et de vente, stop, objectif, horaires) ; le code les vérifie et Friday affiche **ce qu'il a compris**, en français, avec ses interprétations. Chaque plan traduit devient une stratégie : « **teste le plan Cassure Londres sur l'or** », « **compare les stratégies sur l'or** » (tous tes plans face aux stratégies de base), « choisis le plan Cassure Londres pour l'or ». Un plan modifié depuis sa traduction est signalé. *Ma stratégie* choisit celle suivie par défaut (alertes, check-list, briefing, et le plan joint aux analyses de Claude) ; la *gestion du risque* (stop minimal, objectif, risque, trades ouverts, annonces) vaut pour toutes. Ton plan unique d'avant est repris comme « Mon plan », avec sa traduction. **Journal de trading** (*Réglages → Trading → Ouvrir le journal*, ou « ouvre mon journal » en mode trading) : ton bilan en R (réussite, moyenne, total), la **courbe de tes résultats** (total en R trade après trade), tous tes trades, un formulaire vérifié pour en noter un (stop et objectif du bon côté), la clôture au prix de sortie (résultat en R calculé sur le PC), la suppression en deux clics, l'export CSV pour Excel ; la fenêtre suit les trades notés à la voix. **Le journal apprend** : pour chaque trade, note le setup, si le plan a été respecté et ton état d'esprit (« j'ai acheté l'or à 4 130 stop 4 110, c'était un repli EMA50, plan respecté, j'étais calme », ou plus tard « pour le trade 2, j'étais impatient ») ; si TradingView affiche l'instrument, une capture d'entrée est gardée sur le PC. Les statistiques par setup, instrument, heure, jour, plan et état d'esprit apparaissent dans la fenêtre (« Ce que dit le journal »), avec des constats calculés sur le PC dès 3 trades par catégorie (ex. « plan respecté : +1,25 R en moyenne ; non respecté : −1,00 R », « le setup cassure perd en moyenne : à revoir, ou à abandonner »). « Fais ma revue de la semaine » l'envoie à Claude, après aperçu : un bilan **anonyme**, en R, sans prix, montant ni raison écrite, et Claude répond par ce qui marche, ce qui coûte et une ou deux actions pour la semaine. Hors du mode, rien ne change.
- **Cours** : « combien vaut l'or ? », « le cours de l'euro dollar ? » — lu à la source (Yahoo Finance, et cours de référence BCE pour les devises), jamais dans des extraits de recherche web.
- **Bibliothèque** : dépose tes PDF, livres, cours et notes dans `data/bibliotheque` (ou *Réglages → Bibliothèque → Ajouter*) : Friday les indexe en local. Quand un document parle clairement du sujet de ta question, elle y cherche **d'office** avant de répondre, sans qu'il faille dire « dans ma bibliothèque » ; pour l'actualité (« aujourd'hui », « en ce moment »…), c'est internet. Elle cite la source. Recherche par le sens et par les mots exacts (sigles, termes techniques) ; « rien de pertinent » plutôt qu'une réponse inventée. Retirer un document le déplace dans `_retires` (jamais effacé). *Ajouter la bibliothèque de trading* télécharge 26 documents **légalement gratuits** (Wikipédia, AMF, Banque de France, Réserve fédérale, BRI), source et licence en tête de chaque fichier ; les livres de référence s'achètent : voir [docs/livres-trading.md](docs/livres-trading.md). Indexation sur le processeur (~0,2 s par passage, un livre de 300 pages ≈ 2–3 min, en arrière-plan).
- **Longues recherches** : « approfondis le résultat 3 » plusieurs échanges plus tard (carnet de recherche), « garde ces points de côté » (notes), et les vieux échanges résumés automatiquement au lieu d'être oubliés

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

### Mémoire de travail doublée (facultatif, carte de 8 Go)

Ollama peut compresser la mémoire de travail du modèle (perte de qualité imperceptible) : on
passe de 8 192 à **16 384 jetons** dans la même mémoire vidéo, pour de longues conversations
et des pages entières. Dans les variables d'environnement Windows (compte utilisateur) :
`OLLAMA_FLASH_ATTENTION=1` et `OLLAMA_KV_CACHE_TYPE=q8_0`, redémarrer Ollama, puis choisir
16 384 dans *Réglages → Général* (ou `OLLAMA_NUM_CTX=16384` dans `.env`). Au démarrage, Friday
prévient dans le journal si le modèle déborde de la carte graphique (elle serait alors lente).
Mesuré sur RTX 3070 : 6,3 Go, 100 % carte graphique, ~57 jetons/s (contre 58,9 à 8 192).

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
`data/google_token.json`. Autorisations demandées : agenda (lecture et écriture), mails (lecture,
envoi, étiquettes et corbeille ; jamais d'effacement définitif).

## Utilisation

```
uv run friday          # application de bureau
uv run friday --cli    # version terminal
```

- **Mains libres** : dire « **Friday** » (à l'anglaise), « quelle heure est-il ? » d'une traite. « Friday » seul → il répond « Oui ? » et écoute la suite. Juste après une réponse, on peut relancer sans redire son nom. Pendant qu'il parle : « Friday, … » lui coupe la parole, « stop » le fait taire.
- **Mémoire** : il retient seul ce qui compte (« 🧠 Mémorisé : … »). « Retiens que… », « Oublie que… », « Qu'est-ce que tu sais sur moi ? »
- **Mémoire vivante** : un fait redit est renforcé, un fait corrigé remplacé (l'ancien reste dans l'historique) ; « D'où tu sais que… ? » ; fiche lisible `data/memoire.md`, rangée par thème
- **Atelier de compétences** : « Crée-toi une compétence pour… » → Claude l'écrit (après ton accord, confiné à un dossier, sans commandes ni internet), Friday inspecte le code (imports et appels interdits refusés), lance ses tests à part sans réseau, puis te propose de l'installer ; « Quelles compétences as-tu apprises ? », « Supprime la compétence … »
- **Scènes plein écran** : la météo en ciel animé (soleil, nuages, pluie, neige, orage, nuit étoilée) ; « Montre-moi la tour Eiffel », « Où se trouve Tokyo ? » → carte 3D qui vole jusqu'au lieu et tourne autour (MapLibre + OpenFreeMap, gratuit, sans clé) ; « Ferme », « reviens » ou Échap → retour à la sphère
- **Routines** : « Tous les jours à 7 h, donne-moi la météo », « Le vendredi à 18 h, fais-moi le bilan de ma semaine de trading » — Friday le fait seule à l'heure dite (rattrapé si le PC était éteint depuis moins de 3 h) ; « Quelles sont mes routines ? », « Supprime la routine des mails »
- **Sphère de particules** (ou l'hologramme, au choix dans Réglages → Apparence) qui réagit à la voix ; au démarrage, les particules convergent pendant que l'auto-test défile ; fenêtre agrandie : carte « En écoute » (Spotify, YouTube… via Windows) avec lecture/pause, suivant, précédent
- **Double clap** : deux claquements de mains = « Friday » (sensibilité réglable, avec les mains libres)
- **Rêve nocturne** : la nuit (ou après 30 min sans parler), Friday relit la journée, retient ce qu'elle avait manqué et prépare un rapport de ménage (contradictions, faits à reconfirmer, erreurs répétées) qu'elle propose sans rien changer seule — « Qu'as-tu fait cette nuit ? »
- **Mémoire de la journée** : « De quoi on a parlé hier ? », « Qu'est-ce que je t'ai demandé lundi ? » — nos échanges sont gardés 90 jours sur le PC (désactivable dans Réglages → Fonctions)
- **Rappels et listes** : « minuteur de 10 minutes », « rappelle-moi d'appeler maman demain à 18 h », « ajoute du lait à ma liste de courses », « qu'y a-t-il sur ma liste ? ». À l'heure dite : carillon puis annonce vocale.
- **PC** : « ouvre Spotify », « ferme Discord » (avec confirmation), « ouvre YouTube », « mets le volume à 30 », « coupe le son », « musique suivante », « mets du jazz ».
- **Claude Code** : « Friday, demande à Claude d'écrire… » → il demande confirmation (« oui », ou bouton), Claude travaille en arrière-plan dans `CLAUDE_WORKSPACE`, et Friday prévient quand c'est fini. Utilise le CLI `claude` connecté au compte Pro, sans clé API.
- **Fichiers et presse-papier** : glisser un PDF, un document Word ou un fichier texte dans la fenêtre, puis « résume-le », « quelle est la date limite ? ». « Corrige ce que j'ai copié et remets-le dans le presse-papier », « traduis en anglais ce que j'ai copié », « explique le code que j'ai copié ». **Retrouver un fichier** dans Documents, Bureau, Téléchargements et Images : « trouve mon devis de mars », « où est ma photo de vacances ? », « cherche le document où je parle du carrelage », puis « ouvre-le » ou « résume-le ».
- **Voir l'écran** : « regarde mon écran », « c'est quoi cette erreur ? », « pourquoi mon code plante ? », « résume l'article que j'ai à l'écran ». Lu par un petit modèle de vision local (`ollama pull qwen3-vl:4b-instruct`) : la capture ne quitte pas le PC. Compter ~15 s (les deux modèles se relaient sur la carte graphique). En secours : « demande à Claude de regarder mon écran » (avec confirmation, la capture part alors en ligne).
- **Voir une image** : colle une capture dans la barre (Ctrl+V), colle le chemin d'une image (`file:///…png`, `C:\…\photo.jpg`) ou glisse-la dans la fenêtre, puis demande ce que tu veux (« choisis 5 numéros et 2 étoiles d'après cette grille »). Le même modèle de vision local la décrit, rien ne part en ligne. Les images collées sont gardées dans `data/cache/images` (les 20 dernières).
- **Briefing du matin** : au premier démarrage de Friday le matin (5 h – 12 h), une fois par jour, elle présente les rubriques choisies ; une rubrique vide est passée sous silence, et si tout est vide elle ne dit rien. À la voix : « mon briefing », « ajoute la météo de Bordeaux / l'actualité tech / ma liste de tâches / une citation à mon briefing », « retire… », « qu'y a-t-il dans mon briefing ? », « désactive le briefing ». Réglages dans `data/briefing.json`.
- **Agenda et mails Google** : « qu'est-ce que j'ai demain / cette semaine ? », « ajoute dentiste jeudi à 14 h », « déplace / supprime mon rendez-vous de jeudi » (avec confirmation), « ai-je de nouveaux mails ? », « lis-moi le mail de Julie », « réponds-lui que c'est d'accord » (brouillon montré, envoi seulement après « oui »), « trie mes mails » (étiquettes « Friday/… » dans Gmail), « montre les mails de la catégorie banque », « supprime les promotions / les mails de Rollercoin » (corbeille, après confirmation). Rubriques « agenda » et « mails » possibles dans le briefing.
- **Réflexion** : pour un calcul (« combien de jours entre… », « vitesse moyenne… ») ou si on lui dit « réfléchis », « analyse », Friday prend 10 à 20 s pour réfléchir (« Laissez-moi réfléchir… ») : nettement plus juste. Le reste du temps, elle répond tout de suite.
- **Réglages** : icône ⚙️ dans la barre de titre (ou « ouvre les réglages ») : couleur, nom, ville, voix et vitesse, micro et sortie audio, mains libres, briefing et ses rubriques, fonctions à activer, compte Google. Écrits dans `.env` (toujours modifiable à la main) ; ceux qui demandent un redémarrage proposent « Redémarrer Friday ».
- **Push-to-talk** : maintenir la touche `Début` (réglable via `PTT_KEY`), parler, relâcher.
- **Dictée partout** : maintenir la touche `Ctrl` de droite (réglable via `DICTATION_KEY` ou Réglages → Voix, vide = désactivée), parler, relâcher : le texte s'écrit dans la fenêtre active, là où est le curseur (Discord, Word, navigateur…). Whisper seul, rien en ligne. Dire « à la ligne », « point à la ligne » ou « nouveau paragraphe » pour revenir à la ligne.
- **Interprète** : « Friday, traduis la vidéo » (ou « traduis ce que j'entends », « mode interprète ») : le son du PC est écouté, Whisper écrit ce qui est dit, qwen le traduit de l'anglais vers le français et la traduction s'affiche en sous-titres en bas de l'écran, même sur une vidéo en plein écran. « Arrête de traduire » pour finir. Tout reste sur le PC. La sortie écoutée se règle dans Réglages → Voix (« Son traduit par l'interprète »), par défaut celle de Windows.
- **Écrire** : taper son message puis Entrée.

Dans la fenêtre, les boutons de la barre du bas permettent d'envoyer, de parler (maintenir 🎙), de couper la voix et de démarrer une nouvelle conversation. En mode terminal : `/voix` (activer/couper la voix), `/reset` (nouvelle conversation), `/quit` (quitter).

Choisir le micro : `uv run python -m sounddevice` liste les périphériques, puis régler `MIC_DEVICE` (numéro ou morceau du nom).

Choisir la sortie audio : `OUTPUT_DEVICE` (même principe). En cas de grésillements : `uv run python -m friday.voice.diagnostic`.

Pour comparer les voix disponibles : `uv run python -m friday.voice.audition`, puis régler `TTS_VOICE` dans `.env`.

### Notifications Windows

Quand une analyse de Claude, une alerte de trading, un rappel, le briefing trading ou la traduction d'un plan arrive et que Friday n'est pas au premier plan (réduite, derrière TradingView…), une bulle Windows le dit en une phrase ; un clic dessus (ou sur l'icône de Friday près de l'horloge) la ramène devant. Désactivable : *Réglages → Fonctions → Notifications Windows*.

### Limites Claude à l'écran

Fenêtre agrandie, un panneau montre ce qu'il te reste de ta **session Claude** (5 h) et de ta **semaine**, avec l'heure de remise à zéro (vert, orange sous 50 %, rouge sous 20 %). Les chiffres viennent de Claude Code lui-même : *Réglages → Diagnostic → Brancher Claude Code* ajoute à sa ligne d'état un petit relais (copie de sécurité de ses réglages d'abord : `~/.claude/settings.json.avant-friday`), qui les note dans `data/claude_limits.json` et les affiche aussi sous sa zone de saisie. Ils se mettent à jour quand tu utilises Claude Code ; sinon Friday montre les derniers connus, avec leur âge, et remet une fenêtre à 100 % une fois son heure de remise à zéro passée.

### Connecteurs MCP

Friday se branche à des serveurs **MCP** (des outils d'autres services : TradingView, GitHub, Notion…). Le plus simple : *Réglages → Connecteurs → Ajouter un connecteur*, avec des connecteurs tout prêts (Notion, Heure, TradingView) ou le sien (une adresse en ligne, ou un programme sur ce PC et ses clés). *Outils* coche ceux que qwen reçoit (une jauge montre leur poids), *Supprimer* le retire. Le tout est gardé dans `data/mcp.json`, qu'on peut aussi écrire à la main (*Ouvrir le fichier*) :

```json
{"serveurs": {"notes": {"commande": "npx", "arguments": ["-y", "un-serveur-mcp"],
                        "description": "mes notes", "mots_cles": ["note"]}}}
```

Un serveur local se lance par `commande` (et `arguments`, `env`), un serveur distant se joint par `url`. Puis *Rebrancher* : chaque serveur montre son état et ses outils, avec un interrupteur. Ses outils ne sont donnés à qwen que quand la demande en parle (mots-clés, description) ; un outil qui ne se déclare pas en lecture seule demande toujours « oui » avant. Le fichier n'est pas copié dans les sauvegardes (ses `env` peuvent porter des clés). Un serveur distant qui demande un compte (OAuth) s'affiche « à connecter » : *Se connecter* ouvre le navigateur, on accepte, et c'est branché. Le jeton reste sur ce PC (`data/mcp_comptes/`, jamais copié dans les sauvegardes) et se renouvelle tout seul ; *Se déconnecter* l'oublie. Au démarrage, Friday n'ouvre jamais le navigateur de lui-même.

### Fiabilité

- **Ollama surveillé** : si sa vitesse s'effondre deux réponses de suite (modèle à moitié sorti de la carte graphique), Friday recharge le modèle tout seul.
- **Sauvegarde quotidienne** de `data/` (journal de trading, plans et stratégies, mémoire, agenda, notes, réglages) dans `data/sauvegardes` : au démarrage si la dernière a plus de 24 h, puis chaque jour ; les 7 dernières sont gardées. *Réglages → Fonctions → Copie des sauvegardes* : un dossier OneDrive ou une clé USB en plus. Pas les caches, les modèles, la bibliothèque (tes PDF restent ailleurs) ni les clés de connexion Google. Pour restaurer : dézipper l'archive dans `data/`, Friday fermée.
- **Réglages → Diagnostic** : Ollama, modèles, part du modèle dans la carte graphique, vitesse, carte graphique (mémoire, température), voix et micro, dernière sauvegarde ; boutons *Sauvegarder maintenant* et *Recharger le modèle*.

## Développement

Une branche par brique, une PR vers `main`, merge quand la CI est verte.

```
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # mise en forme
```
