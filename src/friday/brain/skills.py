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
CORE_TOOLS = ("close_popups", "remember", "forget_memory", "list_memories", "load_skill")
CORE_GUIDE = """- close_popups : fermer les fenêtres que tu as affichées (résultats, fichiers, météo…).
  Jamais close_app pour elles."""

SKILLS = (
    Skill("web", "internet : météo, recherche, actualité, pages web, images",
          ("get_weather", "web_search", "read_webpage", "search_images"),
          """- get_weather : la météo (actuelle et sur 7 jours). Toujours cet outil pour la météo,
  jamais la recherche web.
- web_search : chercher sur internet : actualité, faits récents, prix, horaires, résultats
  sportifs, ou dès que tu as un doute. Ne réponds jamais de mémoire à une question
  d'actualité : cherche d'abord.
- read_webpage : lire une page précise (un lien donné, ou un résultat à approfondir).
- search_images : montrer des images à l'écran.""",
          ("meteo", "quel temps", "temps qu", "pluie", "pleu", "neige", "temperature", "degre",
           "vent ", "cherche", "recherche", "internet", "web", "actualit", "info ", "infos",
           "news", "nouvelles", "page", "lien", "article", "image", "photo ", "photos", "prix",
           "horaire", "resultat", "match", "score", "qui a gagne", "ligue", "championnat",
           "election", "qui est", "combien coute", "wikipedia", "bourse", "cours de", "cours du",
           "bitcoin", "crypto"),
          ("quel temps fait-il demain", "cherche les dernières nouvelles sur la bourse",
           "montre-moi des images de chats", "qui a gagné le match hier soir",
           "lis-moi cet article")),
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
  Images), avec un mois ou une année si l'utilisateur en parle. Si rien n'est trouvé,
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
- media_control : lancer la lecture, pause, piste suivante ou précédente (Spotify, YouTube…).
- play_music : chercher une musique ou une playlist dans Spotify (ouvre la recherche).""",
          ("ouvre", "ferme", "lance", "quitte", "demarre", "appli", "logiciel", "programme",
           "volume", "son ", "le son", "muet", "monte", "baisse", "musique", "chanson",
           "spotify", "playlist", "pause", "reprends", "suivant", "precedent", "youtube",
           "navigateur", "site", "discord", "steam", "chrome"),
          ("ouvre Spotify", "mets le volume à 30", "ferme Discord", "musique suivante",
           "lance YouTube")),
    Skill("reminders", "minuteurs, rappels, notes et listes de Friday",
          ("set_timer", "set_reminder", "list_reminders", "cancel_reminder",
           "add_note", "list_notes", "remove_note"),
          """- set_timer, set_reminder, list_reminders, cancel_reminder : minuteurs et rappels. Pour
  un rappel, donne l'heure (« 18:00 ») et le jour (« demain », « lundi »), ou le délai
  (« 2 minutes »), EXACTEMENT comme l'utilisateur les a dits : ne convertis rien.
- add_note, list_notes, remove_note : notes et listes (courses, tâches…).""",
          ("rappel", "minuteur", "timer", "alarme", "chrono", "note", "liste", "course",
           "tache", "achete", "dans 5 minutes", "dans 10 minutes", "previens moi"),
          ("rappelle-moi d'appeler maman à 18 h", "minuteur de 10 minutes",
           "ajoute du lait à ma liste de courses", "qu'y a-t-il sur ma liste")),
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
          ("morning_briefing", "configure_briefing"),
          """- morning_briefing : le briefing du matin sur demande (« mon briefing », « quoi de neuf
  aujourd'hui ? »). configure_briefing : ajouter / retirer une rubrique (météo, agenda,
  mails, rappels, une liste, l'actualité d'un sujet, une rubrique libre), les lister,
  activer ou désactiver le briefing automatique. Dès que l'utilisateur parle de SON
  briefing (« ajoute l'actualité tech à mon briefing »), c'est configure_briefing : jamais
  web_search ni get_weather.""",
          ("briefing", "rubrique", "quoi de neuf", "bonjour friday"),
          ("fais-moi mon briefing", "ajoute la météo à mon briefing", "désactive le briefing")),
    Skill("claude", "Claude Code : coder, créer ou modifier des fichiers, longues tâches",
          ("ask_claude_code", "cancel_claude_task"),
          """- ask_claude_code : confier une tâche de programmation ou de création de fichiers à Claude
  Code (code, scripts, documents longs). Écris-lui une consigne complète. L'utilisateur
  confirme avant le lancement ; Claude travaille en arrière-plan et tu seras prévenu à la
  fin. cancel_claude_task l'arrête.""",
          ("claude", "code", "script", "programme qui", "developpe", "cree un fichier",
           "ecris un fichier", "site web", "python"),
          ("demande à Claude d'écrire un script", "crée-moi un programme qui trie mes photos")),
)  # fmt: skip

BY_NAME = {skill.name: skill for skill in SKILLS}
