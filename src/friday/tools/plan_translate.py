"""Outil du mode trading : « traduis le plan Cassure Londres » (ou le bouton de Réglages →
Trading). Le plan écrit part à Claude isolé APRÈS aperçu (masqué comme une question) ; ses
règles, vérifiées par le code, en font une stratégie : backtest, comparaison, alertes,
check-list, briefing."""

import logging
import threading

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.claude_code import ClaudeCodeJob, OnDone
from friday.trading.context_builder import Item, Packet
from friday.trading.masking import mask_personal
from friday.trading.plan_book import PREFIX
from friday.trading.plan_translate import QUESTION, TranslationError, parse
from friday.trading.strategies.spec import describe

log = logging.getLogger(__name__)


def which_plan(choice, plan: str = "", request: str = "") -> dict | None:
    """Le plan voulu : nommé (id ou nom dans la phrase), sinon le seul, sinon celui suivi."""
    book = choice.book
    found = book.get(plan) or book.find(plan) or book.find(request)
    if found:
        return found
    plans = book.plans()
    if len(plans) == 1:
        return plans[0]
    followed = choice.default().name
    return book.get(followed[len(PREFIX) :]) if followed.startswith(PREFIX) else None


class TranslatePlanTool(Tool):
    name = "translate_plan"
    description = (
        "Traduit un plan de trading écrit de l'utilisateur en règles exécutables (« traduis mon "
        "plan », « traduis le plan Cassure Londres ») : backtest, alertes, check-list."
    )
    parameters = {
        "plan": {"type": "string", "description": "Le nom du plan, s'il le dit"},
        "request": {"type": "string", "description": "La phrase de l'utilisateur"},
    }
    needs_confirmation = True  # le plan part en ligne : TOUJOURS après aperçu

    def __init__(self, choice, job: ClaudeCodeJob, journal, on_done: OnDone,
                 blocklist: tuple[str, ...] = ()) -> None:  # fmt: skip
        self.choice, self.job, self.journal = choice, job, journal
        self.on_done, self.blocklist = on_done, blocklist
        self._pending: Packet | None = None
        self._plan: dict | None = None

    def label(self, args: dict) -> str:
        return "📝 Traduction d'un plan en règles (après aperçu)"

    def confirmation(self, args: dict) -> str | None:
        self._pending, self._plan = None, which_plan(self.choice, args.get("plan", ""),
                                                     args.get("request", ""))  # fmt: skip
        if self._plan is None or not self._plan["texte"].strip():
            return None  # rien à envoyer : run() dit pourquoi
        masked = mask_personal(self._plan["texte"], self.blocklist)
        source = f"ton plan « {self._plan['nom']} »"
        self._pending = Packet(QUESTION, [Item("plan", source, masked.text)],
                               masked=list(masked.found))  # fmt: skip
        return (f"J'envoie {source} à Claude pour le traduire en règles. Vérifie l'aperçu : "
                "j'envoie ?")  # fmt: skip

    def preview(self, args: dict) -> Packet | None:
        return self._pending

    def run(self, plan: str = "", request: str = "") -> ToolResult:
        packet, self._pending = self._pending, None
        if packet is None:
            names = ", ".join(f"« {p['nom']} »" for p in self.choice.book.plans())
            if self._plan is not None:
                why = f"Le plan « {self._plan['nom']} » est vide : écris-le d'abord."
            elif names:
                why = f"Quel plan dois-je traduire ? Tes plans : {names}."
            else:
                why = "Tu n'as encore aucun plan écrit : crée-le dans Réglages → Trading."
            return ToolResult(f"Dis EXACTEMENT : « {why} »")
        if not packet.approved:  # garde-fou : jamais sans validation
            return ToolResult("Rien n'a été envoyé : l'envoi n'a pas été validé.")
        if self.job.busy:
            return ToolResult("Claude traduit déjà un plan. Propose d'attendre.")
        content = packet.render()
        sent_id = self.journal.log_sent(packet.question, content)
        self.job.task = packet.question
        threading.Thread(target=self._work, args=(content, sent_id, dict(self._plan)),
                         daemon=True, name="plan-translate").start()  # fmt: skip
        # Constaté : « dis-le en une phrase » → le modèle annonçait des règles inventées (stop,
        # objectif) avant la réponse de Claude ; la vraie arrive plus tard (on_done)
        return ToolResult("Dis EXACTEMENT : « C'est parti : Claude traduit ton plan, je te "
                          "préviens dès que c'est prêt. »")  # fmt: skip

    def _work(self, content: str, sent_id: int, plan: dict) -> None:
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
                f"Dis EXACTEMENT : « La traduction du plan « {plan['nom']} » a échoué : {error} "
                "Rien n'a changé. »"))  # fmt: skip
            return
        self.choice.book.save_translation(plan["id"], spec, plan["texte"])
        lines = describe(spec)
        spoken = (f"Le plan « {plan['nom']} » est traduit en règles : {lines[0]}. Le détail de "
                  "ce que j'ai compris est affiché ; vérifie-le. Dis « teste le plan "
                  f"{plan['nom']} » pour le backtester, ou « compare les "
                  "stratégies ».")  # fmt: skip
        items = [{"text": line.split(" : ")[0], "meta": line.split(" : ", 1)[-1]}
                 for line in lines]  # fmt: skip
        self.on_done("traduction du plan", ToolResult(
            f"Dis EXACTEMENT : « {spoken} »",
            Display("items", f"Plan « {plan['nom']} », traduit en règles",
                    {"icon": "📝", "items": items})))  # fmt: skip
