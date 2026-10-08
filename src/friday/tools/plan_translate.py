"""Outil du mode trading : « traduis mon plan » (ou le bouton de Réglages → Trading). Le plan
écrit part à Claude isolé APRÈS aperçu (masqué comme une question) ; ses règles, vérifiées par
le code, deviennent la stratégie « ton plan écrit » : backtest, alertes, check-list, briefing."""

import logging
import threading

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.claude_code import ClaudeCodeJob, OnDone
from friday.trading.context_builder import Item, Packet
from friday.trading.context_sources import load_plan
from friday.trading.masking import mask_personal
from friday.trading.plan_translate import QUESTION, TranslationError, parse
from friday.trading.strategies.spec import describe

log = logging.getLogger(__name__)


class TranslatePlanTool(Tool):
    name = "translate_plan"
    description = (
        "Traduit le plan de trading écrit de l'utilisateur en règles exécutables (« traduis mon "
        "plan ») : elles servent ensuite au backtest, aux alertes et à la check-list."
    )
    parameters = {}
    needs_confirmation = True  # le plan part en ligne : TOUJOURS après aperçu

    def __init__(self, plan_path, choice, job: ClaudeCodeJob, journal, on_done: OnDone,
                 blocklist: tuple[str, ...] = ()) -> None:  # fmt: skip
        self.plan_path, self.choice, self.job = plan_path, choice, job
        self.journal, self.on_done, self.blocklist = journal, on_done, blocklist
        self._pending: Packet | None = None

    def label(self, args: dict) -> str:
        return "📝 Traduction du plan en règles (après aperçu)"

    def confirmation(self, args: dict) -> str | None:
        plan = load_plan(self.plan_path) if self.plan_path else ""
        if not plan:
            self._pending = None
            return None  # rien à envoyer : run() le dit
        masked = mask_personal(plan, self.blocklist)
        self._pending = Packet(QUESTION, [Item("plan", "ton plan de trading", masked.text)],
                               masked=list(masked.found))  # fmt: skip
        self._plan = plan
        return (
            "J'envoie ton plan à Claude pour le traduire en règles. Vérifie l'aperçu : j'envoie ?"
        )

    def preview(self, args: dict) -> Packet | None:
        return self._pending

    def run(self) -> ToolResult:
        packet, self._pending = self._pending, None
        if packet is None:
            return ToolResult("Dis EXACTEMENT : « Ton plan de trading est vide : écris-le dans "
                              "Réglages → Trading → Mon plan de trading. »")  # fmt: skip
        if not packet.approved:  # garde-fou : jamais sans validation
            return ToolResult("Rien n'a été envoyé : l'envoi n'a pas été validé.")
        if self.job.busy:
            return ToolResult("Claude traduit déjà ton plan. Propose d'attendre.")
        content = packet.render()
        sent_id = self.journal.log_sent(packet.question, content)
        self.job.task = packet.question
        threading.Thread(target=self._work, args=(content, sent_id, self._plan), daemon=True,
                         name="plan-translate").start()  # fmt: skip
        return ToolResult("C'est envoyé : Claude traduit ton plan (moins d'une minute en "
                          "général). Dis-le en une phrase.")  # fmt: skip

    def _work(self, content: str, sent_id: int, plan: str) -> None:
        try:
            outcome = self.job.run(content)
        except Exception as error:
            log.exception("Échec de la traduction du plan")
            outcome = {"ok": False, "result": f"Erreur : {error}"}
        finally:
            self.job.task = None
        self.journal.log_answer(sent_id, outcome["result"])
        try:
            if not outcome["ok"]:
                raise TranslationError(outcome["result"][:300])
            spec = parse(outcome["result"])
        except TranslationError as error:
            self.on_done("traduction du plan", ToolResult(
                f"Dis EXACTEMENT : « La traduction de ton plan a échoué : {error} Rien n'a "
                "changé. »"))  # fmt: skip
            return
        self.choice.save_translation(spec, plan)
        lines = describe(spec)
        spoken = (f"Ton plan est traduit en règles : {lines[0]}. Le détail de ce que j'ai "
                  "compris est affiché ; vérifie-le. Dis « teste mon plan » pour le backtester, "
                  "ou « compare les stratégies ».")  # fmt: skip
        items = [{"text": line.split(" : ")[0], "meta": line.split(" : ", 1)[-1]}
                 for line in lines]  # fmt: skip
        self.on_done(
            "traduction du plan",
            ToolResult(
                f"Dis EXACTEMENT : « {spoken} »",
                Display("items", "Ton plan, traduit en règles", {"icon": "📝", "items": items}),
            ),
        )
