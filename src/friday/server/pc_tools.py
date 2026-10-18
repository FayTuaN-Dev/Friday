"""Les outils du Friday du Pi pour le PC (R4) : « allume le PC », « le PC est allumé ? »,
« éteins le PC » (toujours après un « oui », confirmé sur le téléphone)."""

import time

from friday.server.pc_link import PcLink
from friday.tools.base import Tool, ToolResult

BOOT_WAIT = 150  # secondes : un PC qui démarre met ~1 à 2 min à répondre
POLL = 5


class WakePcTool(Tool):
    name = "wake_pc"
    description = "Allume le PC de la maison à distance (« allume le PC », « démarre mon PC »)."
    parameters = {}
    timeout = BOOT_WAIT + 30

    def __init__(self, link: PcLink, sleep=time.sleep) -> None:
        self.link, self.sleep = link, sleep

    def label(self, args: dict) -> str:
        return "🖥️ Allumage du PC"

    def run(self) -> ToolResult:
        if self.link.state(fresh=True):
            return ToolResult("Dis EXACTEMENT : « Le PC est déjà allumé. »")
        try:
            self.link.wake()
        except (OSError, ValueError) as error:
            return ToolResult(f"Dis EXACTEMENT : « Je n'arrive pas à réveiller le PC ({error}). »")
        for _ in range(BOOT_WAIT // POLL):
            self.sleep(POLL)
            if self.link.state(fresh=True):
                return ToolResult("Dis EXACTEMENT : « Le PC est allumé. Sa carte graphique "
                                  "m'aidera à répondre plus vite. »")  # fmt: skip
        return ToolResult("Dis EXACTEMENT : « J'ai envoyé le signal de réveil, mais le PC ne "
                          f"répond pas après {BOOT_WAIT // 60} minutes. Le réveil par le réseau "
                          "est-il activé dans le BIOS ? »")  # fmt: skip


class PcStateTool(Tool):
    name = "pc_state"
    description = "Dit si le PC de la maison est allumé (« le PC est allumé ? »)."
    parameters = {}

    def __init__(self, link: PcLink) -> None:
        self.link = link

    def label(self, args: dict) -> str:
        return "🖥️ État du PC"

    def run(self) -> ToolResult:
        seen = self.link.state(fresh=True)
        if not seen:
            return ToolResult("Dis EXACTEMENT : « Le PC est éteint. »")
        session = "quelqu'un est connecté" if seen.get("session") else "personne n'est connecté"
        brain = ("je pense avec sa carte graphique" if self.link.can_think()
                 else "sa carte graphique est occupée, je pense avec la mienne")  # fmt: skip
        return ToolResult(f"Dis EXACTEMENT : « Le PC est allumé ; {session} ; {brain}. »")


class ShutdownPcTool(Tool):
    name = "shutdown_pc"
    description = "Éteint le PC de la maison à distance (« éteins le PC »), après confirmation."
    parameters = {}
    needs_confirmation = True

    def __init__(self, link: PcLink) -> None:
        self.link = link

    def label(self, args: dict) -> str:
        return "🖥️ Extinction du PC"

    def confirmation(self, args: dict) -> str:
        seen = self.link.state(fresh=True) or {}
        warn = (" Attention : une session est ouverte, le travail non enregistré sera perdu."
                if seen.get("session") else "")  # fmt: skip
        return f"J'éteins le PC dans une minute ?{warn}"

    def run(self) -> ToolResult:
        if not self.link.state(fresh=True):
            return ToolResult("Dis EXACTEMENT : « Le PC est déjà éteint. »")
        if not self.link.shutdown(60):
            return ToolResult("Dis EXACTEMENT : « Le PC n'a pas accepté l'extinction. »")
        return ToolResult("Dis EXACTEMENT : « Le PC s'éteint dans une minute. »")
