"""Outils de l'atelier de compétences (J8) : « crée-toi une compétence pour… » (Claude
l'écrit, après accord), « installe-la » (après inspection et tests, avec accord), « quelles
compétences as-tu apprises ? », « supprime la compétence … ». Phrases construites par le code."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime

from friday.skills_lab.contract import RULES, WRITER, task
from friday.skills_lab.lab import Check, Lab
from friday.tools.base import Tool, ToolResult
from friday.tools.claude_code import ClaudeCodeJob

log = logging.getLogger(__name__)

TASK = "atelier"  # tâche de fond (notification « 🧪 Compétence »)


def rights_text(check: Check) -> str:
    return "accès à internet" if "internet" in check.inspection.rights else "aucun accès extérieur"


def verdict(check: Check) -> str:
    """La phrase dite quand Claude a fini."""
    total = check.passed + check.failed
    if check.ok:
        return (f"Dis EXACTEMENT : « La compétence « {check.name} » est prête : "
                f"{check.info.get('resume', '').rstrip('.')}. Droits : {rights_text(check)}. "
                f"Tests : {check.passed} réussis sur {total}. Dis « installe-la » si tu la "
                "veux. »")  # fmt: skip
    if not check.inspection.ok:
        why = f"son code fait des choses interdites ({check.inspection.problems[0]})"
    elif total:
        why = f"{check.failed} test{'s' if check.failed > 1 else ''} sur {total} échoue(nt)"
    else:
        why = "ses tests ne se lancent pas"
    return (f"Dis EXACTEMENT : « Je n'installe pas cette compétence : {why}. Dis « réessaie » "
            "pour que Claude la corrige. »")  # fmt: skip


class CreateSkillTool(Tool):
    name = "create_skill"
    description = (
        "Fait écrire par Claude une NOUVELLE compétence (un nouvel outil) pour toi, quand "
        "l'utilisateur te demande d'apprendre à faire quelque chose que tu ne sais pas faire "
        "(« crée-toi une compétence pour suivre mes colis »), ou de réessayer la dernière."
    )
    parameters = {
        "goal": {"type": "string", "description": "Ce que la compétence doit faire, précisément"}
    }
    required = ("goal",)
    needs_confirmation = True  # utilise le quota Claude de l'utilisateur

    def __init__(self, lab: Lab, model: str, timeout: float,
                 on_done: Callable[[str, ToolResult], None]) -> None:  # fmt: skip
        self.lab, self.model, self.timeout, self.on_done = lab, model, timeout, on_done
        self.working = False
        self.last_goal = ""

    def label(self, args: dict) -> str:
        return f"🧪 Nouvelle compétence : {args.get('goal', '')}"

    def confirmation(self, args: dict) -> str:
        goal = args.get("goal", "").strip().rstrip(".!? ")
        return (f"Je demande à Claude d'écrire une compétence : {goal}. Elle sera inspectée et "
                "testée avant que je te propose de l'installer. Je lance ?")  # fmt: skip

    def run(self, goal: str) -> ToolResult:
        if self.working:
            return ToolResult("Claude écrit déjà une compétence : propose d'attendre.")
        retry = goal.strip().lower() in ("", "réessaie", "reessaie", "la dernière") or (
            goal.strip() == self.last_goal)  # fmt: skip
        last = self.lab.last
        errors = last.problems() if retry and last is not None and not last.ok else ""
        goal = self.last_goal if retry and self.last_goal else goal
        self.working, self.last_goal = True, goal
        threading.Thread(target=self._work, args=(goal, errors), daemon=True,
                         name="atelier").start()  # fmt: skip
        return ToolResult("C'est lancé : Claude écrit la compétence en arrière-plan (quelques "
                          "minutes), puis je l'inspecte et la teste. Dis-le en une phrase."
                          )  # fmt: skip

    def _work(self, goal: str, errors: str) -> None:
        try:
            folder = self.lab.new_draft(datetime.now().strftime("%Y%m%d-%H%M%S"))
            job = ClaudeCodeJob(folder, self.model, self.timeout, options=WRITER,
                                instructions=RULES)  # fmt: skip
            outcome = job.run(task(goal, errors))
            if not outcome.get("ok"):
                text = (
                    f"Dis EXACTEMENT : « Claude n'a pas pu écrire la compétence : "
                    f"{outcome.get('result', '')[:200]} »"
                )
            else:
                text = verdict(self.lab.check(folder))
        except Exception as error:
            log.exception("Atelier : échec")
            text = f"Dis EXACTEMENT : « L'atelier a échoué : {error}. »"
        finally:
            self.working = False
        self.on_done(TASK, ToolResult(text))


class InstallSkillTool(Tool):
    name = "install_skill"
    description = "Installe la compétence que Claude vient d'écrire (« installe-la »)."
    parameters = {}
    needs_confirmation = True

    def __init__(self, lab: Lab, on_install: Callable[[list[Tool]], None]) -> None:
        self.lab, self.on_install = lab, on_install

    def label(self, args: dict) -> str:
        return "🧪 Installation de la compétence"

    def confirmation(self, args: dict) -> str:
        check = self.lab.last
        if check is None or not check.ok:
            return "Aucune compétence n'est prête à installer. Je vérifie quand même ?"
        return (f"J'installe la compétence « {check.name} » ({rights_text(check)}, "
                f"{check.passed} tests réussis) ?")  # fmt: skip

    def run(self) -> ToolResult:
        check = self.lab.last
        if check is None or not check.ok:
            return ToolResult("Dis EXACTEMENT : « Aucune compétence n'est prête à installer. »")
        try:
            folder = self.lab.install(check)
            info, tools = self.lab.load(folder)
        except Exception as error:
            return ToolResult(f"Dis EXACTEMENT : « Installation impossible : {error}. »")
        self.on_install(tools)
        self.lab.last = None
        example = (info.get("exemples") or [""])[0]
        hint = f" Essaie par exemple : « {example} »." if example else ""
        summary = info.get("resume", check.name).rstrip(".").lower()
        return ToolResult(f"Dis EXACTEMENT : « C'est installé : je sais maintenant {summary}."
                          f"{hint} »")  # fmt: skip


class ListLearnedSkillsTool(Tool):
    name = "list_learned_skills"
    description = (
        "Les compétences apprises dans l'atelier (« quelles compétences as-tu apprises ? »)."
    )
    parameters = {}

    def __init__(self, lab: Lab) -> None:
        self.lab = lab

    def label(self, args: dict) -> str:
        return "🧪 Compétences apprises"

    def run(self) -> ToolResult:
        loaded = self.lab.load_all()
        if not loaded:
            return ToolResult("Dis EXACTEMENT : « Je n'ai encore appris aucune compétence. »")
        names = " ; ".join(f"{info.get('nom', f.name)} : {info.get('resume', '').rstrip('.')}"
                           for f, info, _ in loaded)  # fmt: skip
        return ToolResult(f"Dis EXACTEMENT : « Mes compétences apprises : {names}. »")


class RemoveLearnedSkillTool(Tool):
    name = "remove_learned_skill"
    description = "Supprime une compétence apprise (« supprime la compétence des colis »)."
    parameters = {"about": {"type": "string", "description": "Son nom ou ce qu'elle fait"}}
    required = ("about",)

    def __init__(self, lab: Lab, on_remove: Callable[[list[str]], None]) -> None:
        self.lab, self.on_remove = lab, on_remove

    def label(self, args: dict) -> str:
        return f"🧪 Suppression : {args.get('about', '')}"

    def run(self, about: str) -> ToolResult:
        from friday.skills_lab.lab import slug

        wanted = {w for w in slug(about).split("-") if len(w) > 3}
        found = [(f, info, tools) for f, info, tools in self.lab.load_all()
                 if wanted & set(slug(f"{info.get('nom', '')} {info.get('resume', '')} "
                                      f"{f.name}").split("-"))]  # fmt: skip
        if len(found) != 1:
            return ToolResult("Rien supprimé : précise le nom de la compétence (liste-les).")
        folder, info, tools = found[0]
        self.lab.remove(folder)
        self.on_remove([t.name for t in tools])
        return ToolResult(f"Dis EXACTEMENT : « Compétence « {info.get('nom', folder.name)} » "
                          "supprimée. »")  # fmt: skip
