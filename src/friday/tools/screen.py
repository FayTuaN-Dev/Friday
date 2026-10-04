"""Outils : regarder l'écran (vision locale), ou le confier à Claude en secours."""

from collections.abc import Callable
from datetime import datetime

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.claude_code import ClaudeCodeTool
from friday.vision.reader import ScreenReader, VisionUnavailable

Capture = Callable[[], bytes]


def screen_display(image: bytes) -> Display:
    return Display("screen", "Ce que je vois", {"image": image})


class LookAtScreenTool(Tool):
    name = "look_at_screen"
    description = (
        "Regarde l'écran de l'utilisateur (capture lue sur l'ordinateur, rien n'est envoyé en "
        "ligne) : « regarde mon écran », « c'est quoi cette erreur ? », « explique ce que je "
        "vois », « résume cette page »."
    )
    parameters = {"question": {"type": "string", "description": "Ce que l'utilisateur veut savoir"}}
    timeout = 60  # chargement du modèle de vision compris

    def __init__(self, reader: ScreenReader, capture: Capture) -> None:
        self.reader = reader
        self.capture = capture

    def label(self, args: dict) -> str:
        return "👁️ Je regarde l'écran"

    def run(self, question: str = "") -> ToolResult:
        image = self.capture()
        try:
            description = self.reader.describe(image, question)
        except VisionUnavailable as error:
            return ToolResult(f"{error} Préviens l'utilisateur.")
        return ToolResult(
            f"Ce que montre l'écran (lu par le modèle de vision) :\n{description}\n\n"
            "Réponds à l'utilisateur à partir de cette description, en faisant toi-même les "
            "calculs éventuels. Sois brève : deux ou trois phrases (l'essentiel), sauf s'il "
            "demande des détails ; la capture est déjà affichée. Si la description ne suffit "
            "pas, dis-le et propose de demander à Claude de regarder l'écran.",
            screen_display(image),
        )


class AskClaudeAboutScreenTool(Tool):
    name = "ask_claude_about_screen"
    description = (
        "En secours : envoie une capture de l'écran à Claude (en ligne, plus intelligent) "
        "quand look_at_screen n'a pas suffi, ou si l'utilisateur demande que Claude regarde."
    )
    parameters = {"question": {"type": "string", "description": "Ce que l'utilisateur veut savoir"}}
    needs_confirmation = True  # la capture quitte l'ordinateur et consomme le quota

    def __init__(self, claude: ClaudeCodeTool, capture: Capture) -> None:
        self.claude = claude
        self.capture = capture
        self._pending: bytes | None = None

    def label(self, args: dict) -> str:
        return "🤖 Claude regarde l'écran"

    def confirmation(self, args: dict) -> str:
        # Capture AVANT de poser la question : sinon la carte « Je lance ? » serait dessus.
        self._pending = self.capture()
        return "J'envoie une capture de votre écran à Claude, en ligne. Je lance ?"

    def run(self, question: str = "") -> ToolResult:
        image, self._pending = self._pending or self.capture(), None
        folder = self.claude.job.workspace / "captures"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"ecran-{datetime.now():%Y%m%d-%H%M%S}.png"
        path.write_bytes(image)
        task = (
            f"Lis l'image « {path} » (une capture de l'écran de l'utilisateur) avec ton outil "
            f"de lecture, puis réponds en français à cette question : "
            f"{question or 'que vois-tu ?'} Réponds en quelques phrases, sans créer ni "
            "modifier de fichier."
        )
        return self.claude.run(task)
