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
        Field("HOME_CITY", "Ville par défaut (météo)", "text",
              help="Vide : Friday utilise la ville qu'elle a mémorisée."),
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
        Field("MIC_DEVICE", "Micro", "choice", options=lambda: audio_devices(True)),
        Field("OUTPUT_DEVICE", "Sortie audio de Friday", "choice",
              options=lambda: audio_devices(False)),
        Field("PTT_KEY", "Touche à maintenir pour parler", "text", "home",
              "home, f9, right ctrl, page up…"),
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
        Field("GOOGLE_ENABLED", "Agenda et mails Google", "bool", "true"),
        Field("CLAUDE_ENABLED", "Délégation à Claude Code", "bool", "true"),
        Field("MEMORY_ENABLED", "Mémoire à long terme", "bool", "true"),
        Field("MEMORY_AUTO", "Mémorisation automatique", "bool", "true"),
        Field("LIBRARY_ENABLED", "Bibliothèque de documents", "bool", "true"),
        Field("TRADING_ENABLED", "Mode trading (« mode trading »)", "bool", "true",
              "Analyses par Claude après aperçu ; calculs et journal en local."),
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
        Field("FRED_API_KEY", "Clé FRED (gratuite)", "text", "",
              "Résultats publiés des annonces américaines. Clé sur fredaccount.stlouisfed.org "
              "→ API Keys."),
        Field("TRADING_CAPTURE_WINDOW", "Fenêtre du graphique (titre)", "text", "TradingView",
              "Seule cette fenêtre est capturée, quand la question parle du graphique. "
              "« TradingView » reconnaît aussi un onglet au titre « EURUSD 1,1258 ▲ +0.36% »."),
    )),
)  # fmt: skip
