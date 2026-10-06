"""Outil : analyse de trading par Claude (en mode trading). Le paquet est construit et montré
dans l'aperçu au moment de la confirmation ; il ne part que s'il a été validé."""

import logging
import threading

from friday.brain import safety
from friday.tools.base import Display, Tool, ToolResult
from friday.tools.claude_code import LLM_MAX_CHARS, ClaudeCodeJob, OnDone
from friday.trading.context_builder import ContextBuilder, Packet
from friday.trading.journal import TradeJournal

log = logging.getLogger(__name__)
JOURNAL_WORDS = ("mes trades", "mon journal", "mes resultats", "mes performances", "mon bilan")


class TradingAnalysisTool(Tool):
    name = "trading_analysis"
    description = (
        "En mode trading : fait analyser une question de trading par Claude, avec les extraits "
        "de la bibliothèque. L'utilisateur voit et valide ce qui part avant l'envoi."
    )
    parameters = {"question": {"type": "string", "description": "La question de l'utilisateur"}}
    required = ("question",)
    needs_confirmation = True  # TOUJOURS : rien ne part sans validation

    def __init__(
        self, builder: ContextBuilder, job: ClaudeCodeJob, journal: TradeJournal, on_done: OnDone
    ) -> None:
        self.builder, self.job, self.journal, self.on_done = builder, job, journal, on_done
        self._pending: Packet | None = None

    def label(self, args: dict) -> str:
        return "📈 Analyse par Claude (après aperçu)"

    def confirmation(self, args: dict) -> str:
        question = str(args.get("question", ""))
        words = question.lower()
        self._pending = self.builder.build(question, with_journal=any(w in words for w in
                                                                      JOURNAL_WORDS))  # fmt: skip
        extracts = sum(1 for i in self._pending.items if i.kind == "extrait")
        masked = (
            f", {len(self._pending.masked)} donnée(s) masquée(s)" if self._pending.masked else ""
        )
        return (
            f"J'envoie cette question à Claude, en ligne, avec {extracts} extrait(s) de votre "
            f"bibliothèque{masked}. Vérifiez l'aperçu : j'envoie ?"
        )

    def preview(self, args: dict) -> Packet | None:
        return self._pending

    def run(self, question: str) -> ToolResult:
        packet, self._pending = self._pending, None
        if packet is None or not packet.approved:  # garde-fou : jamais sans validation
            log.warning("Analyse de trading NON envoyée : pas de validation")
            return ToolResult("Rien n'a été envoyé : l'envoi n'a pas été validé.")
        if self.job.busy:
            return ToolResult("Claude analyse déjà une question. Propose d'attendre.")
        content = packet.render()
        sent_id = self.journal.log_sent(packet.question, content, packet.images)
        self.job.task = packet.question
        threading.Thread(target=self._work, args=(packet.question, content, sent_id),
                         daemon=True, name="trading-claude").start()  # fmt: skip
        return ToolResult(
            "C'est envoyé : Claude analyse (en général moins d'une minute). Dis-le en une "
            "phrase ; tu liras sa réponse quand elle arrivera."
        )

    def _work(self, question: str, content: str, sent_id: int) -> None:
        try:
            outcome = self.job.run(content)
        except Exception as error:
            log.exception("Échec de l'analyse de trading")
            outcome = {"ok": False, "result": f"Erreur : {error}"}
        finally:
            self.job.task = None
        answer = outcome["result"][:LLM_MAX_CHARS]
        self.journal.log_answer(sent_id, answer)
        text = (
            "Réponse de Claude, ton analyste de trading, à la question « "
            f"{question} » :\n{safety.wrap_external(answer)}\n"
            "Résume-la à l'oral en trois ou quatre phrases, en gardant ses mises en garde et "
            "ses sources ; le détail est affiché. Ce n'est jamais un ordre ni un signal."
        )
        display = Display("claude", f"Analyse : {question}", {**outcome, "files": []})
        self.on_done(question, ToolResult(text, display))
