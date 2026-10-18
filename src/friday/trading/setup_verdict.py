"""L'avis de Claude sur chaque setup de la surveillance (P3) : OUI ou NON, et pourquoi.

Envoi AUTOMATIQUE, sans aperçu : seulement si l'utilisateur l'a activé (Réglages → Trading →
« Avis de Claude sur chaque setup »), au plus N fois par jour. Ce qui part est le paquet
habituel des analyses (setup, cours et indicateurs publics, annonces, marchés liés, plan
suivi, extraits de la bibliothèque), MASQUÉ comme toujours, et noté au journal des envois.
Claude reste isolé (aucun outil, rien d'autre que répondre : analyst.py).

Ce n'est pas un ordre : l'avis sert à mesurer, dans le carnet, si filtrer les setups avec
Claude améliore vraiment les résultats (« bilan des setups »)."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from friday.tools.claude_code import ClaudeCodeJob
from friday.trading.analyst import ISOLATED
from friday.trading.analyst import RULES as ANALYST

log = logging.getLogger(__name__)
REASON_CHARS = 400

RULES = (
    ANALYST
    + """

Cette fois, Friday te soumet un SETUP détecté par sa surveillance, selon la stratégie suivie
par l'utilisateur. Réponds UNIQUEMENT par un objet JSON, sans texte autour :
{"avis": "oui" ou "non", "raison": "deux phrases au plus, en français : pourquoi"}
- « oui » : le setup respecte le plan fourni et rien de grave ne s'y oppose (annonce à fort
  impact imminente, marchés liés franchement contraires, niveau qui invalide tout proche).
- « non » sinon. Dans le doute, « non ».
- Pas de taille de position ni de calcul : Friday s'en charge. Ce n'est jamais un ordre."""
)


def verdict_job(workspace: Path, model: str, timeout: float) -> ClaudeCodeJob:
    return ClaudeCodeJob(workspace, model, timeout, options=ISOLATED, instructions=RULES)


def parse_verdict(answer: str) -> tuple[str, str] | None:
    """(« oui » ou « non », raison) ; None si la réponse ne se lit pas."""
    start, end = answer.find("{"), answer.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(answer[start : end + 1])
            avis = str(data.get("avis", "")).strip().lower()
            if avis in ("oui", "non"):
                return avis, str(data.get("raison", "")).strip()[:REASON_CHARS]
        except ValueError:
            pass
    found = re.match(r"\s*\**\s*(oui|non)\b[\s.:,!*—-]*(.*)", answer, re.I | re.S)
    if found:  # « OUI : … » sans JSON
        return found.group(1).lower(), found.group(2).strip()[:REASON_CHARS]
    return None


class SetupJudge:
    """Demande l'avis de Claude sur un setup du carnet (appelé hors du fil principal)."""

    def __init__(self, builder, job: ClaudeCodeJob, journal=None, per_day: int = 10) -> None:
        """`builder` : ContextBuilder (le paquet masqué) ; `journal` : le journal des envois."""
        self.builder, self.job, self.journal, self.per_day = builder, job, journal, per_day
        self._asked: list[str] = []  # dates des demandes (limite par jour)

    def reserve(self, now: datetime) -> bool:
        """Un avis de plus aujourd'hui ? (compté dès la mise en file : constaté, compté à
        l'envoi, 6 setups d'un coup passaient tous malgré une limite de 2)"""
        today = f"{now:%Y-%m-%d}"
        self._asked = [d for d in self._asked if d == today]
        if len(self._asked) >= self.per_day:
            return False
        self._asked.append(today)
        return True

    def judge(self, entry: dict, instrument, now: datetime) -> tuple[str, str] | None:
        question = (f"Setup détecté par la surveillance de Friday : {entry['text']} Selon mon "
                    "plan et le contexte, puis-je prendre ce trade ?")  # fmt: skip
        packet = self.builder.build(question, instrument=instrument)
        content = packet.render()
        sent = None
        if self.journal is not None:
            sent = self.journal.log_sent(packet.question, content, [], packet.instrument,
                                         packet.price)  # fmt: skip
        try:
            outcome = self.job.run(content)
        except Exception:
            log.exception("Avis de Claude sur un setup impossible")
            return None
        answer = str(outcome.get("result", ""))
        if sent is not None:
            self.journal.log_answer(sent, answer)
        found = parse_verdict(answer) if outcome.get("ok", True) else None
        if found is None:
            log.warning("Avis de Claude illisible : %s", answer[:200])
        return found
