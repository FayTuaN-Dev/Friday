"""Les compétences de Friday : chacune regroupe ses outils, ses consignes pour le modèle,
des mots-clés et des phrases d'exemple pour l'aiguillage.

Un modèle 8B se trompe d'autant plus qu'il voit d'outils (et leurs descriptions prenaient
plus de 5 000 jetons sur 8 192) : à chaque demande, seules les compétences utiles lui sont
données (voir router.py).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    label: str  # une ligne, pour que le modèle sache ce qu'il peut charger (load_skill)
    tools: tuple[str, ...]
    guide: str  # consignes d'utilisation, ajoutées au prompt quand la compétence est active
    keywords: tuple[str, ...] = ()  # débuts de mots, sans accents (« rappel » → rappelle…)
    examples: tuple[str, ...] = ()  # pour l'aiguillage par le sens (embeddings)


# Toujours présents : petits et utiles partout.
CORE_TOOLS = (
    "close_popups", "open_settings", "remember", "forget_memory", "list_memories", "load_skill",
    "recall_day", "memory_origin", "dream_report", "open_memory_sheet",
)  # fmt: skip
CORE_GUIDE = """- close_popups : fermer les fenêtres que tu as affichées (résultats, fichiers, météo…).
  Jamais close_app pour elles.
- open_settings : ouvrir la fenêtre des réglages (« ouvre les réglages », « les paramètres »).
- recall_day : nos échanges d'un jour passé (« de quoi on a parlé hier ? »).
- memory_origin : d'où vient un souvenir (« d'où tu sais que… ? »).
- dream_report : ce que tu as fait cette nuit (relu la journée, souvenirs à vérifier)."""

SKILLS = (
    Skill("web", "internet : météo, recherche, actualité, pages web, images, cartes",
          ("get_weather", "web_search", "read_webpage", "search_images", "market_quote",
           "show_place", "show_route", "show_weather_map", "show_planes", "plane_overhead"),
          """- get_weather : la météo (actuelle et sur 7 jours). Toujours cet outil pour la météo,
  jamais la recherche web.
- web_search : chercher sur internet : actualité, faits récents, prix, horaires, résultats
  sportifs, ou dès que tu as un doute. Ne réponds jamais de mémoire à une question
  d'actualité : cherche d'abord.
- read_webpage : lire une page précise (un lien donné, ou un résultat à approfondir).
- search_images : montrer des images à l'écran.
- market_quote : le cours d'une devise, de l'or, de l'argent, du pétrole, d'un indice, d'une
  crypto ou d'une action. Toujours cet outil pour un cours, jamais web_search.
- show_place : MONTRER un lieu réel sur une carte 3D (« montre-moi la tour Eiffel », « où se
  trouve Tokyo ? »). Pour des PHOTOS d'un lieu, c'est search_images.
- show_route : un ITINÉRAIRE tracé sur la carte, avec distance et durée (« trace-moi la route
  de Nantes à Lyon », « combien de temps pour aller à Bordeaux ? », « c'est loin, Brest ? »).
  Départ non dit = chez l'utilisateur (laisse origin vide). Jamais de mémoire : cet outil.
- show_weather_map : MONTRER le vent et/ou les températures sur une carte (« montre-moi le
  vent », « la carte des températures en France », « le vent en Bretagne »). Pour la météo
  d'une ville en mots (« quel temps fait-il ? »), c'est get_weather.
- show_planes : MONTRER les avions en vol, en direct, sur une carte (« montre les avions
  au-dessus de la France », « le trafic aérien en Europe »).
- plane_overhead : l'avion qui passe au-dessus d'un lieu, avec son vol (« c'est quoi l'avion
  au-dessus de chez moi ? »). Lieu non dit = chez l'utilisateur (laisse place vide).""",
          ("meteo", "quel temps", "temps qu", "pluie", "pleu", "neige", "temperature", "degre",
           "vent ", "cherche", "recherche", "internet", "web", "actualit", "info ", "infos",
           "news", "nouvelles", "page", "lien", "article", "image", "photo ", "photos", "prix",
           "horaire", "resultat", "match", "score", "qui a gagne", "ligue", "championnat",
           "election", "qui est", "combien coute", "wikipedia", "bourse", "cours de", "cours du",
           "taux de change", "combien vaut", "l or ", "argent metal", "petrole", "bitcoin",
           "matieres premieres", "devise",
           "bitcoin", "crypto", "approfondi", "en savoir plus", "plus de detail", "developpe",
           "guide", "le point", "numero", "montre moi", "fais moi voir", "ou se trouve",
           "ou est situe", "carte", "en 3d", "vue du ciel", "itineraire", "trajet",
           "la route", "pour aller", "c est loin", "combien de km", "kilometres", "distance",
           "en voiture", "a velo", "a pied", "trace moi", "le vent", "du vent",
           "les vents", "temperatures", "carte meteo", "carte des", "avion", "trafic aerien",
           "vol ", "vols ", "aeroport"),
          ("quel temps fait-il demain", "cherche les dernières nouvelles sur la bourse",
           "montre-moi des images de chats", "qui a gagné le match hier soir",
           "lis-moi cet article", "montre-moi la tour Eiffel",
           "trace-moi la route jusqu'à Nantes", "combien de temps pour aller à Bordeaux",
           "montre-moi le vent", "la carte des températures en France",
           "montre les avions au-dessus de la France", "c'est quoi l'avion au-dessus de chez moi")),
    Skill("monde", "actualité internationale, catastrophes, ce qui peut bouger les marchés",
          ("world_news", "market_movers", "show_world"),
          """- world_news : le point sur le monde (« quoi de neuf dans le monde ? », « les infos
  internationales », « il y a eu un séisme ? »). Répète la phrase telle quelle.
- market_movers : ce qui, dans l'actualité, peut bouger les marchés (« qu'est-ce qui peut
  bouger les marchés ? », « quoi de neuf pour l'or ? »). Répète la phrase telle quelle.
- show_world : MONTRER le monde sur un globe plein écran (« montre-moi ce qui se passe dans
  le monde »). Répète la phrase telle quelle.
- Pour un sujet précis (« les dernières nouvelles sur Apple »), c'est web_search.""",
          ("dans le monde", "actualite internationale", "actualites internationales",
           "infos internationales", "info internationale", "nouvelles du monde", "geopoliti",
           "bouger les marches", "bouge les marches", "bouger mes marches", "fait bouger",
           "seisme", "tremblement de terre", "catastrophe", "cyclone", "ouragan", "typhon",
           "eruption", "volcan", "inondation", "globe", "carte du monde"),
          ("quoi de neuf dans le monde", "qu'est-ce qui peut bouger les marchés aujourd'hui",
           "il y a eu un séisme ?", "les infos internationales")),
    Skill("screen", "voir l'écran de l'utilisateur",
          ("look_at_screen", "ask_claude_about_screen"),
          """- look_at_screen : regarder l'écran de l'utilisateur (« regarde mon écran », « c'est quoi
  cette erreur ? », « explique ce que je vois »). Lu sur l'ordinateur, rien ne part en ligne.
- ask_claude_about_screen : en secours seulement, si look_at_screen n'a pas suffi ou si
  l'utilisateur demande que Claude regarde (la capture part en ligne, il confirme avant).""",
          ("ecran", "regarde", "vois", "capture", "affiche a l ecran", "cette erreur"),
          ("regarde mon écran", "c'est quoi cette erreur", "explique ce que je vois",
           "résume ce que j'ai sous les yeux")),
    Skill("files", "fichiers et presse-papier : lire, chercher, ouvrir, copier",
          ("read_file", "read_clipboard", "copy_to_clipboard", "search_files", "open_file"),
          """- read_file : lire un fichier (PDF, Word, texte) pour le résumer, le traduire ou répondre
  dessus. Un fichier glissé dans la fenêtre arrive comme « [Fichier joint : chemin] ».
- Ce que l'utilisateur a copié arrive souvent dans sa demande, comme « [Texte copié par
  l'utilisateur : …] » : sers-t'en directement. Sinon, read_clipboard le lit. Ne lui demande
  jamais de coller le texte : tu peux le lire toi-même.
- search_files : retrouver un fichier par son nom (Documents, Bureau, Téléchargements,
  Images, Musique), avec un mois ou une année si l'utilisateur en parle. Si rien n'est trouvé,
  relance avec in_content=true pour chercher dans le contenu des documents.
- open_file : ouvrir un fichier (ou son dossier avec reveal=true), à partir de son chemin.
- copy_to_clipboard : mettre un texte dans le presse-papier (corrigé, traduit, rédigé…).
  Si l'utilisateur demande de le mettre, remettre ou copier dans le presse-papier, appelle
  copy_to_clipboard avec le texte complet. Ne dis JAMAIS qu'un texte est dans le
  presse-papier sans avoir appelé cet outil.""",
          ("fichier", "document", "pdf", "word", "docx", "dossier", "copie", "presse papier",
           "colle", "telecharg", "bureau", "devis", "facture pdf", "traduis", "corrige",
           "resume", "numero"),
          ("trouve mon devis de mars", "résume ce document", "corrige ce que j'ai copié",
           "ouvre le fichier", "traduis ce texte en anglais")),
    Skill("pc", "l'ordinateur : applications, sites, volume, musique",
          ("open_app", "close_app", "open_website", "set_volume", "media_control", "play_music"),
          """- open_app / close_app : ouvrir ou fermer une application (fermer demande confirmation).
- open_website : ouvrir un site dans le navigateur.
- set_volume : régler, monter, baisser ou couper le son, de tout le PC ou d'une seule
  application (« app »). Jamais media_control pour le volume.
- media_control : reprendre la lecture, pause, piste suivante ou précédente (Spotify,
  YouTube…), SANS rien choisir.
- play_music : LANCER une musique précise sur Spotify : playlist (« lance Nova », « ma
  playlist chill »), album (« mets l'album Discovery »), artiste (« mets du Daft Punk »),
  titre. Donne la demande telle quelle dans query. Tu peux lancer de la musique : ne dis
  jamais le contraire. Répète la phrase donnée telle quelle.""",
          ("ouvre", "ferme", "lance", "quitte", "demarre", "appli", "logiciel", "programme",
           "volume", "son ", "le son", "muet", "monte", "baisse", "musique", "chanson",
           "spotify", "playlist", "pause", "reprends", "suivant", "precedent", "youtube",
           "navigateur", "site", "discord", "steam", "chrome", "album", "morceau", "artiste",
           "ecouter", "mets du ", "mets de la ", "mets des ", "mets moi du", "mets moi de la",
           "joue ", "un peu de "),
          ("ouvre Spotify", "mets le volume à 30", "ferme Discord", "musique suivante",
           "lance YouTube", "mets du Daft Punk", "mets l'album Discovery")),
    Skill("reminders", "minuteurs, rappels, notes et listes de Friday",
          ("set_timer", "set_reminder", "list_reminders", "cancel_reminder",
           "add_note", "list_notes", "remove_note"),
          """- set_timer, set_reminder, list_reminders, cancel_reminder : minuteurs et rappels. Pour
  un rappel, donne l'heure (« 18:00 ») et le jour (« demain », « lundi »), ou le délai
  (« 2 minutes »), EXACTEMENT comme l'utilisateur les a dits : ne convertis rien. Une
  alerte à une heure (« mets une alerte à 7 h ») est un rappel : set_reminder.
- add_note, list_notes, remove_note : notes et listes (courses, tâches…).
- Quand l'utilisateur demande de sauvegarder, garder ou mettre de côté des informations
  (par exemple les points d'intérêt d'une recherche) : appelle add_note pour chacune, dans
  une liste au nom du sujet. Sans appel à add_note, rien n'est enregistré : ne prétends
  pas l'avoir fait.""",
          ("rappel", "minuteur", "timer", "alarme", "chrono", "note", "liste", "course",
           "tache", "achete", "dans 5 minutes", "dans 10 minutes", "previens moi", "sauvegard",
           "point d interet", "points d interet", "de cote", "garde moi", "garde ces",
           "alerte a ", "alerte pour", "alerte demain", "alerte ce soir"),
          ("rappelle-moi d'appeler maman à 18 h", "minuteur de 10 minutes",
           "ajoute du lait à ma liste de courses", "qu'y a-t-il sur ma liste")),
    Skill("routines", "routines : demandes que Friday fait seule, régulièrement, à heure fixe",
          ("add_routine", "list_routines", "remove_routine"),
          """- add_routine : quand l'utilisateur veut que tu fasses quelque chose RÉGULIÈREMENT à
  heure fixe (« tous les jours à 7 h, fais-moi mon briefing », « chaque lundi à 8 h, trie
  mes mails »). request = l'action seule, avec ses mots ; time = l'heure ; days = les jours
  EXACTEMENT comme dits. Ne fais PAS l'action maintenant : programme-la.
- list_routines, remove_routine : voir et supprimer les routines.""",
          ("routine", "tous les jours", "tous les matins", "tous les soirs", "chaque jour",
           "chaque matin", "chaque soir", "chaque lundi", "chaque semaine", "tous les lundis",
           "tous les mardis", "tous les mercredis", "tous les jeudis", "tous les vendredis",
           "tous les samedis", "tous les dimanches", "en semaine", "le week end", "programme",
           # « le vendredi à 18 h, fais… » : en français, une habitude
           "le lundi a", "le mardi a", "le mercredi a", "le jeudi a", "le vendredi a",
           "le samedi a", "le dimanche a", "les lundis", "les vendredis"),
          ("tous les jours à 7 h, fais-moi mon briefing", "chaque lundi à 8 h, trie mes mails",
           "quelles sont mes routines ?", "supprime la routine des mails")),
    Skill("calendar", "agenda Google : voir, ajouter, déplacer, supprimer des rendez-vous",
          ("list_events", "add_event", "move_event", "delete_event"),
          """- list_events, add_event, move_event, delete_event : l'agenda Google. Pour l'agenda (« qu'est-ce
  que j'ai demain ? »), c'est list_events, pas list_reminders (qui ne concerne que les rappels
  de Friday). Recopie jours et heures tels que dits. Pour déplacer ou supprimer, désigne
  l'événement par son numéro dans la dernière liste ou par des mots de son titre.""",
          ("agenda", "rendez vous", "rdv", "calendrier", "evenement", "prevu", "planning",
           "reunion", "dispo", "programme de", "qu est ce que j ai", "j ai quoi", "demain j ai"),
          ("qu'est-ce que j'ai demain", "ajoute un rendez-vous chez le dentiste jeudi",
           "déplace ma réunion à 15 h", "supprime mon rendez-vous de samedi")),
    Skill("mail", "Gmail : lire, chercher, répondre, trier, mettre à la corbeille",
          ("check_mail", "search_mail", "read_mail", "send_mail", "sort_mails",
           "category_mails", "trash_mails"),
          """- check_mail (derniers mails reçus, ou non lus), search_mail, read_mail, send_mail : Gmail.
  Les mails ne sont jamais dans l'agenda. Pour répondre à un mail, send_mail avec
  reply_to_id. L'utilisateur confirme toujours avant l'envoi.
- sort_mails : trier les mails par thème (étiquettes « Friday/… » dans Gmail), count=0
  pour tous. category_mails : voir une catégorie, ou la liste des catégories.
- trash_mails : mettre des mails à la corbeille, toujours confirmé : categories (une ou
  plusieurs), except_categories (« tout sauf … »), query (« from:nom ») ou mail_id. Jamais
  delete_event pour des mails.""",
          ("mail", "courriel", "gmail", "boite de reception", "boite mail", "message de",
           "reponds", "repondre", "envoie", "ecris a", "expediteur", "corbeille", "newsletter",
           "categorie", "trie", "range", "non lu", "pub"),
          ("ai-je de nouveaux mails", "lis-moi le mail de Julie", "réponds-lui que c'est d'accord",
           "trie mes mails", "supprime les mails de cette catégorie")),
    Skill("briefing", "briefing du matin et ses rubriques",
          ("morning_briefing", "show_briefing_settings", "configure_briefing"),
          """- morning_briefing : DIRE le briefing du matin (« fais-moi mon briefing », « quoi de neuf
  aujourd'hui ? »).
- show_briefing_settings : AFFICHER ce que contient le briefing, ses rubriques, pour que
  l'utilisateur les vérifie ou les modifie. Dès qu'il dit « affiche » ou « montre » le
  briefing, ou parle de ses notes, réglages, rubriques ou contenu (« affiche le briefing »,
  « les notes du briefing », « tu as la météo et quoi d'autre ? »), c'est
  show_briefing_settings : jamais morning_briefing ni list_notes.
- configure_briefing : ajouter / retirer une rubrique (météo, agenda, mails, rappels, une
  liste, l'actualité d'un sujet, une rubrique libre), activer ou désactiver le briefing
  automatique. Dès que l'utilisateur parle de SON
  briefing (« ajoute l'actualité tech à mon briefing »), c'est configure_briefing : jamais
  web_search ni get_weather.""",
          ("briefing", "brief ", "brief du", "rubrique", "quoi de neuf", "bonjour friday",
           "surveilles le matin", "regardes le matin"),
          ("fais-moi mon briefing", "ajoute la météo à mon briefing", "désactive le briefing")),
    Skill("library", "bibliothèque : PDF, livres et cours de l'utilisateur",
          ("search_library", "list_library", "update_library"),
          """- search_library : chercher dans la bibliothèque de l'utilisateur (ses PDF, livres,
  cours). Prioritaire sur internet quand il parle de ses livres ou documents, ou d'un sujet
  qu'il y a rangé. Réponds à partir des passages trouvés et cite la source (document, page).
  Si rien n'est pertinent, dis-le, puis propose de chercher sur internet.
- list_library : ce que contient la bibliothèque. update_library : la mettre à jour.""",
          ("bibliotheque", "mes livres", "mon livre", "le livre", "mes documents", "mes pdf",
           "mes cours", "mon cours", "selon mes", "dans mes notes de cours", "mes fiches"),
          ("que dit mon livre sur la gestion du risque", "cherche dans ma bibliothèque",
           "qu'y a-t-il dans mes documents sur le Forex", "d'après mes cours, c'est quoi un pip")),
    Skill("trading", "trading : calculs de risque, check-list, journal, alertes, backtest, "
          "stratégies, briefing trading",
          ("position_size", "pip_value", "risk_reward", "log_trade", "annotate_trade", "close_trade",
           "trade_stats", "open_journal", "trade_check", "backtest_plan", "set_price_alert",
           "watch_setup", "list_alerts", "cancel_alert", "trading_briefing", "past_analyses",
           "compare_strategies", "choose_strategy", "translate_plan"),
          """- Outils de trading du PC (rien ne part en ligne, sauf translate_plan après aperçu).
  position_size, pip_value, risk_reward : calculs EXACTS faits sur le PC ; extrais les
  chiffres de la demande, n'en invente aucun (demande ceux qui manquent), puis répète le
  résultat tel quel. Jamais de calcul de tête. Le cours n'est jamais à demander : le PC le
  récupère tout seul.
- trade_check : la check-list avant trade. Dès que l'utilisateur décrit une idée de trade
  chiffrée (« je veux acheter l'or à 4 160, stop 4 140 ») ou demande si un trade respecte son
  plan : sens, entrée, stop (et objectif, risque, lots s'il les donne). Répète le feu tel quel.
- backtest_plan : rejouer le plan sur l'historique (« teste mon plan sur l'or », « et avec
  un objectif à 3 R ? »). Répète la phrase donnée telle quelle.
- set_price_alert (« préviens-moi si l'or passe 4 150 »), watch_setup (« surveille l'or » :
  le setup du plan), list_alerts, cancel_alert : les alertes de PRIX, surveillées sur le PC
  et annoncées à la voix (une alerte à une heure est un rappel). Répète la phrase telle quelle.
- compare_strategies (« compare les stratégies sur l'or ») et choose_strategy (« choisis la
  cassure de range pour l'or ») : la bibliothèque de stratégies. Répète la phrase telle quelle.
- translate_plan : traduire son plan écrit en règles (« traduis mon plan »), après aperçu.
- past_analyses : les dernières analyses de Claude et le cours depuis (« mes dernières
  analyses »). Répète la phrase donnée telle quelle.
- trading_briefing : le briefing trading (« briefing trading », « prépare ma journée de
  trading ») ; à ne pas confondre avec le briefing du matin. Répète le texte tel quel.
- log_trade (avec setup, plan respecté, état d'esprit s'il les dit), annotate_trade (les
  ajouter après coup), close_trade, trade_stats (bilan et ce que le journal apprend) : le journal.
  « Note ce trade » / « note le trade » : log_trade (le journal), jamais add_note ; open_journal :
  l'ouvrir à l'écran (« ouvre mon journal »).
- Une question d'analyse de marché (« que penses-tu de l'or ? ») : seul Claude l'analyse, et
  seulement en mode trading ; s'il n'est pas actif, propose de dire « mode trading ».
- Tu ne donnes jamais d'ordre ni de signal ; tu ne passes jamais d'ordre.""",
          ("taille de position", "combien de lots", "nombre de lots", "valeur du pip",
           "valeur d un pip", "pip ", "pips ", "risque rendement", "ratio risque", "risk reward",
           "trade", "journal de trading", "mon journal de", "check list", "checklist",
           "respecte mon plan", "respecte le plan", "mon plan de trading", "backtest", "back test",
           "teste mon plan", "teste le plan", "briefing trading", "brief trading",
           "journee de trading", "mes analyses", "dernieres analyses", "tes analyses",
           "strategie", "setup"),
          ("calcule ma taille de position", "combien vaut un pip sur 0,5 lot",
           "note ce trade dans le journal", "quel est mon bilan de trading",
           "je veux acheter l'or à 4160 stop 4140", "ce trade respecte-t-il mon plan",
           "teste mon plan sur l'historique de l'or", "préviens-moi si l'or passe 4150",
           "quelles alertes de prix j'ai")),
    Skill("analyse_trading", "mode trading : faire analyser une question de marché par Claude",
          ("trading_analysis",),
          """- Mode trading actif. trading_analysis : faire analyser une question de marché par
  Claude (l'utilisateur valide d'abord l'aperçu). Tu ne donnes jamais d'ordre ni de signal.""",
          ("analyse", "ton avis", "que penses"),
          ("que penses-tu de l'or en ce moment", "analyse l'EUR/USD")),
    Skill("claude", "Claude Code : coder, créer ou modifier des fichiers, longues tâches",
          ("ask_claude_code", "cancel_claude_task", "create_skill", "install_skill",
           "list_learned_skills", "remove_learned_skill"),
          """- ask_claude_code : confier une tâche de programmation ou de création de fichiers à Claude
  Code (code, scripts, documents longs). Écris-lui une consigne complète. L'utilisateur
  confirme avant le lancement ; Claude travaille en arrière-plan et tu seras prévenu à la
  fin. cancel_claude_task l'arrête.
- create_skill : quand l'utilisateur veut que tu APPRENNES à faire quelque chose de nouveau
  (« crée-toi une compétence pour… », « apprends à… ») ; « réessaie » relance la dernière.
  install_skill : « installe-la » après le compte rendu. list_learned_skills,
  remove_learned_skill : voir et supprimer les compétences apprises.""",
          ("claude", "code", "script", "programme qui", "developpe", "cree un fichier",
           "ecris un fichier", "site web", "python", "competence", "apprends a", "apprendre a",
           "installe la", "reessaie"),
          ("demande à Claude d'écrire un script", "crée-moi un programme qui trie mes photos")),
)  # fmt: skip

BY_NAME = {skill.name: skill for skill in SKILLS}
