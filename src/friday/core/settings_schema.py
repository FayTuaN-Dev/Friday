"""Les réglages modifiables depuis l'écran de réglages : clé du .env, libellé, type, aide.
L'écran se construit à partir de cette liste (ajouter un réglage = ajouter une ligne ici)."""

from collections.abc import Callable
from dataclasses import dataclass, field

from friday.core.config import VOICES_DIR


@dataclass(frozen=True)
class Field:
    key: str  # clé du .env
    label: str
    kind: str  # "bool", "text", "int", "float", "choice"
    default: str = ""
    help: str = ""
    minimum: float = 0
    maximum: float = 100
    step: float = 1
    options: Callable[[], list[tuple[str, str]]] | None = None  # (valeur, libellé)


@dataclass(frozen=True)
class Section:
    name: str
    icon: str  # icône (voir ui/desktop/icons.py)
    fields: tuple[Field, ...] = field(default_factory=tuple)


def voices() -> list[tuple[str, str]]:
    names = sorted(p.name.removesuffix(".onnx") for p in VOICES_DIR.glob("*.onnx"))
    return [(n, n.removeprefix("fr_FR-").replace("-", " · ")) for n in names]


def audio_devices(inputs: bool) -> list[tuple[str, str]]:
    """Périphériques audio (une seule API Windows, sans doublons) ; vide = celui de Windows."""
    import sounddevice as sd

    default_api = sd.default.hostapi
    channels = "max_input_channels" if inputs else "max_output_channels"
    names = []
    for device in sd.query_devices():
        if (
            device["hostapi"] == default_api
            and device[channels] > 0
            and device["name"] not in names
        ):
            names.append(device["name"])
    return [("", "Celui de Windows (par défaut)")] + [(n, n) for n in names]


SECTIONS = (
    Section("Général", "user", (
        Field("FRIDAY_USER_NAME", "Comment Friday vous appelle", "text", "Monsieur"),
        Field("START_WITH_WINDOWS", "Lancer Friday avec Windows", "bool", "true",
              "Elle démarre cachée près de l'horloge et vous écoute tout de suite. La croix de "
              "sa fenêtre la cache ; « Quitter Friday » (clic droit sur l'icône) l'arrête."),
        Field("HOME_CITY", "Ville par défaut (météo, trajets)", "text",
              help="Vide : Friday utilise la ville qu'elle a mémorisée. C'est aussi le point "
                   "de départ des trajets (« il faut partir dans 15 min »)."),
        Field("OLLAMA_NUM_CTX", "Mémoire de travail du modèle", "choice", "8192",
              "Plus grande = conversations et pages plus longues. Au-delà de 8 192 sur une "
              "carte de 8 Go : compression Ollama nécessaire (voir README).",
              options=lambda: [("8192", "8 192 jetons"), ("12288", "12 288 jetons"),
                               ("16384", "16 384 jetons")]),
    )),
    Section("Voix", "volume", (
        Field("TTS_ENABLED", "Friday parle à voix haute", "bool", "true"),
        Field("TTS_VOICE", "Voix", "choice", "fr_FR-siwis-medium", options=voices),
        Field("TTS_SPEED", "Vitesse de parole", "float", "1.0",
              "1,0 = normale ; plus grand = plus lent", 0.6, 1.6, 0.05),
        Field("TTS_NAME_PRONUNCIATION", "Prononciation de son nom", "text", "Fraille dé",
              "Comment la voix française doit dire « Friday »."),
    )),
    Section("Écoute", "mic", (
        Field("HANDS_FREE", "Mains libres (dire « Friday, … »)", "bool", "true"),
        Field("CLAP_WAKE", "Réveil par double clap", "bool", "true",
              "Deux claquements de mains rapprochés = « Friday » (avec les mains libres)."),
        Field("CLAP_SENSITIVITY", "Sensibilité du double clap", "choice", "moyenne",
              "Forte : claps plus doux ou micro loin ; faible si des bruits le réveillent.",
              options=lambda: [("faible", "Faible"), ("moyenne", "Moyenne"),
                               ("forte", "Forte")]),
        Field("MIC_DEVICE", "Micro", "choice", options=lambda: audio_devices(True)),
        Field("OUTPUT_DEVICE", "Sortie audio de Friday", "choice",
              options=lambda: audio_devices(False)),
        Field("INTERPRETER_DEVICE", "Son traduit par l'interprète", "choice", "",
              "La sortie où joue la vidéo (« Friday, traduis la vidéo »).",
              options=lambda: audio_devices(False)),
        Field("PTT_KEY", "Touche à maintenir pour parler", "text", "home",
              "home, f9, right ctrl, page up…"),
        Field("DICTATION_KEY", "Touche de dictée (le texte s'écrit où est le curseur)", "text",
              "right ctrl", "Maintenir, parler, relâcher : dans Discord, Word, le navigateur… "
              "« à la ligne » passe à la ligne. Vide = désactivée."),
        Field("FOLLOW_UP_SECONDS", "Relance sans redire « Friday » (secondes)", "int", "8",
              "0 = toujours redire son nom.", 0, 30),
        Field("VAD_SILENCE_MS", "Silence de fin de phrase (millisecondes)", "int", "700",
              "Plus court = plus réactif, mais risque de couper.", 300, 2000, 50),
    )),
    Section("Fonctions", "sliders", (
        Field("TOOLS_ENABLED", "Internet : météo, recherche, actualités, images", "bool", "true"),
        Field("PC_CONTROL", "Contrôle du PC : applications, volume, musique", "bool", "true"),
        Field("FILES_ACCESS", "Fichiers et presse-papier", "bool", "true"),
        Field("VISION_ENABLED", "Voir l'écran", "bool", "true"),
        Field("AGENDA_ENABLED", "Rappels, minuteurs, notes et listes", "bool", "true"),
        Field("NOTIFICATIONS", "Notifications Windows", "bool", "true",
              "Quand une analyse, une alerte, un rappel ou un briefing arrive et que Friday "
              "n'est pas au premier plan (réduite, derrière TradingView…)."),
        Field("DAY_MEMORY", "Mémoire de la journée", "bool", "true",
              "Garde nos échanges 90 jours sur ce PC (data/journee.db) pour répondre à « de "
              "quoi on a parlé hier ? »."),
        Field("SCENES", "Scènes plein écran", "bool", "true",
              "La météo en ciel animé sur toute la fenêtre (sinon dans une petite fenêtre). Les "
              "lieux (« montre-moi la tour Eiffel ») s'affichent toujours en carte 3D."),
        Field("NIGHT_DREAM", "Rêve nocturne", "bool", "true",
              "La nuit (ou après 30 min sans parler), Friday relit la journée pour retenir ce "
              "qu'elle a manqué et prépare un rapport de ménage, qu'elle propose sans rien "
              "changer seule. Demande « qu'as-tu fait cette nuit ? »."),
        Field("GAME_MODE_AUTO", "Mode jeu automatique", "bool", "true",
              "Quand un jeu se lance, Friday libère la carte graphique d'elle-même. « Friday, "
              "reviens » ou un double clap pour la rappeler."),
        Field("GAME_MODE_IGNORE", "Pas des jeux (mode jeu)", "text", "",
              "Programmes à ne jamais prendre pour un jeu, séparés par des virgules (ex. : "
              "wallpaper64, resolve)."),
        Field("BACKUP_DIR", "Copie des sauvegardes (dossier)", "text", "",
              "Facultatif : un dossier OneDrive ou une clé USB. Les sauvegardes quotidiennes "
              "restent aussi dans data/sauvegardes (les 7 dernières)."),
        Field("GOOGLE_ENABLED", "Agenda et mails Google", "bool", "true"),
        Field("CLAUDE_ENABLED", "Délégation à Claude Code", "bool", "true"),
        Field("MEMORY_ENABLED", "Mémoire à long terme", "bool", "true"),
        Field("MEMORY_AUTO", "Mémorisation automatique", "bool", "true"),
        Field("LIBRARY_ENABLED", "Bibliothèque de documents", "bool", "true"),
        Field("TRADING_ENABLED", "Mode trading (« mode trading »)", "bool", "true",
              "Analyses par Claude après aperçu ; calculs et journal en local."),
    )),
    Section("Initiative", "bulb", (
        Field("INITIATIVE", "Friday prend l'initiative", "bool", "true",
              "Elle parle d'elle-même, à voix haute, quand c'est utile (jamais en mode jeu : "
              "gardé pour votre retour)."),
        Field("INITIATIVE_DEPARTURE", "Heure de départ des rendez-vous", "bool", "true",
              "Pour un événement de l'agenda Google qui a une adresse : « il faudrait partir "
              "dans 15 minutes ». Trajet en voiture depuis la ville par défaut, sans les "
              "bouchons (marge de 15 % + 5 min)."),
        Field("INITIATIVE_WEATHER", "Météo du trajet (voiture ou moto)", "bool", "true",
              "Ajoutée à l'heure de départ : pluie, rafales ou verglas à l'aller ou au retour "
              "→ « la voiture plutôt que la moto » ; sinon « la moto passe »."),
        Field("INITIATIVE_MAILS", "Mails importants", "bool", "true",
              "Un mail non lu d'un expéditeur important, ou avec un mot important dans "
              "l'objet, est annoncé dès son arrivée (vérifié toutes les 2 min)."),
        Field("INITIATIVE_MAIL_SENDERS", "Expéditeurs importants", "text", "",
              "Séparés par des virgules : une adresse (marie@exemple.fr), un domaine "
              "(@impots.gouv.fr) ou un nom (Banque Populaire). Vide : aucun."),
        Field("INITIATIVE_MAIL_WORDS", "Mots importants dans l'objet", "text", "",
              "Séparés par des virgules (ex. : convocation, urgent, colis). Sans accents ni "
              "majuscules à respecter. Vide : aucun."),
        Field("INITIATIVE_QUIET", "Heures calmes", "text", "23-7",
              "Aucune initiative entre ces heures (ex. : 23-7). 0-0 : jamais calme."),
        Field("INITIATIVE_PER_HOUR", "Initiatives par heure, au plus", "int", "4",
              minimum=1, maximum=20),
    )),
    Section("Trading", "trending", (
        Field("TRADING_ACCOUNT_CURRENCY", "Devise du compte", "text", "EUR",
              "Pour la valeur du pip et la taille de position (calculées sur le PC)."),
        Field("TRADING_PASSAGES", "Extraits de la bibliothèque par analyse", "int", "10",
              "Envoyés à Claude avec la question (après aperçu).", 1, 15),
        Field("TRADING_MAX_CHARS", "Taille maximale d'un envoi (caractères)", "int", "12000",
              "Au-delà, les extraits les moins utiles ne partent pas.", 2000, 30000, 1000),
        Field("TRADING_BLOCKLIST", "Mots toujours masqués", "text", "",
              "Séparés par des virgules : votre nom, n° de client du courtier…"),
        Field("TRADING_HOURS", "Mes heures de trading (Paris)", "text", "9-18",
              "Ex. « 9-18 » : Claude en tient compte (une annonce à 20 h ne bloque pas la "
              "journée)."),
        Field("TRADING_BRIEFING", "Briefing trading au début de ma plage", "bool", "true",
              "En semaine, à l'heure de début de vos heures de trading : annonces, nuit, "
              "niveaux clés, tendance, règles du plan. Aussi à la voix : « briefing trading »."),
        Field("TRADING_CLAUDE_VERDICT", "Avis de Claude sur chaque setup", "bool", "false",
              "Chaque setup de la surveillance part AUTOMATIQUEMENT à Claude, sans aperçu "
              "(cours publics, annonces, plan suivi, extraits, masqués comme d'habitude, notés "
              "au journal des envois) : il répond OUI ou NON. Ce n'est pas un ordre."),
        Field("TRADING_VERDICTS_PER_DAY", "Avis de Claude par jour (au plus)", "int", "10",
              "Pour ménager vos limites Claude : au-delà, les setups sont annoncés sans avis.",
              1, 50),
        Field("TRADING_BRIEFING_INSTRUMENTS", "Instruments du briefing trading", "text", "",
              "Ex. « or, EUR/USD ». Vide : ceux que vous surveillez (« surveille l'or »)."),
        Field("FRED_API_KEY", "Clé FRED (gratuite)", "text", "",
              "Résultats publiés des annonces américaines. Clé sur fredaccount.stlouisfed.org "
              "→ API Keys."),
        Field("TRADING_CAPTURE_WINDOW", "Fenêtre du graphique (titre)", "text", "TradingView",
              "Seule cette fenêtre est capturée, quand la question parle du graphique. "
              "« TradingView » reconnaît aussi un onglet au titre « EURUSD 1,1258 ▲ +0.36% »."),
    )),
)  # fmt: skip
