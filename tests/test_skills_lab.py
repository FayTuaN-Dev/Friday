"""Atelier de compétences (J8) : inspection du code (imports, appels, __attributs__), tests à
part sans réseau, installation avec accord, chargement à chaud, ré-inspection à chaque
chargement, suppression ; Claude n'écrit que dans son dossier."""

import threading

from friday.brain.toolset import Toolset
from friday.skills_lab.contract import WRITER, task
from friday.skills_lab.inspection import inspect_skill, inspect_source
from friday.skills_lab.lab import Lab
from friday.tools.base import ToolBox
from friday.tools.skills_lab import (
    CreateSkillTool,
    InstallSkillTool,
    ListLearnedSkillsTool,
    RemoveLearnedSkillTool,
    verdict,
)

SKILL = """from friday.tools.base import Tool, ToolResult
SKILL = {"nom": "Convertisseur de température",
         "resume": "convertir des degrés Celsius en Fahrenheit",
         "mots_cles": ["fahrenheit"], "exemples": ["30 degrés en fahrenheit"]}
class CelsiusTool(Tool):
    name = "celsius_to_fahrenheit"
    description = "Convertit des degrés Celsius en Fahrenheit."
    parameters = {"celsius": {"type": "number", "description": "°C"}}
    required = ("celsius",)
    def run(self, celsius: float) -> ToolResult:
        return ToolResult(f"Dis EXACTEMENT : « {celsius} °C font {celsius * 9 / 5 + 32:g} °F. »")
"""
TESTS = """from skill import CelsiusTool
def test_zero():
    assert "32 °F" in CelsiusTool().run(0).text
def test_hundred():
    assert "212 °F" in CelsiusTool().run(100).text
def test_name():
    assert CelsiusTool().name == "celsius_to_fahrenheit"
"""


def draft(lab: Lab, name: str, skill: str = SKILL, tests: str = TESTS):
    folder = lab.new_draft(name)
    (folder / "skill.py").write_text(skill, "utf-8")
    (folder / "test_skill.py").write_text(tests, "utf-8")
    return folder


def test_the_code_is_inspected_before_anything_runs():
    bad = inspect_source("import os\nimport subprocess\nfrom pathlib import Path\n"
                         "x = eval('1')\ny = open('f')\nz = ().__class__.__subclasses__()\n"
                         "getattr(x, 'a')\n", "skill.py")  # fmt: skip
    text = " | ".join(bad.problems)
    for word in ("« os »", "« subprocess »", "« pathlib »", "« eval »", "« open »",
                 "« __class__ »", "« __subclasses__ »", "« getattr »"):  # fmt: skip
        assert word in text, word
    good = inspect_source("import httpx\nimport json\nfrom friday.tools.base import Tool\n", "s")
    assert good.ok and good.rights == {"internet"}
    assert not inspect_source("import pytest", "skill.py").ok  # pytest : seulement dans les tests
    assert inspect_source("import pytest\nfrom skill import X", "t.py", tests=True).ok
    assert not inspect_skill("x = 1", TESTS).ok  # pas de fiche SKILL
    assert "erreur de syntaxe" in inspect_source("def (", "skill.py").problems[0]


def test_claude_only_writes_files_in_its_folder():
    assert "--restricted" in WRITER and WRITER[WRITER.index("--tools") + 1] == "Read,Write,Edit"
    assert "Bash" not in " ".join(WRITER)
    assert "corrige-les" in task("suivre mes colis", "2 tests échouent")


def test_a_good_skill_is_tested_installed_loaded_and_removed(tmp_path):
    lab = Lab(tmp_path)
    check = lab.check(draft(lab, "essai1"))
    assert check.ok and (check.passed, check.failed) == (3, 0), check.output
    assert check.name == "Convertisseur de température"
    assert verdict(check).startswith("Dis EXACTEMENT : « La compétence « Convertisseur de "
                                     "température » est prête")  # fmt: skip
    assert "aucun accès extérieur" in verdict(check) and "3 réussis sur 3" in verdict(check)
    box = ToolBox([])
    toolset = Toolset(box)
    install = InstallSkillTool(lab, lambda tools: [box.add(t) for t in tools])
    assert "J'installe la compétence « Convertisseur de température »" in install.confirmation({})
    said = install.run().text
    assert said.startswith("Dis EXACTEMENT : « C'est installé : je sais maintenant convertir")
    assert "« 30 degrés en fahrenheit »" in said
    assert "celsius_to_fahrenheit" in toolset.tool_names()  # disponible tout de suite
    assert box.find("celsius_to_fahrenheit").run(celsius=20).text.endswith("68 °F. »")
    assert "Convertisseur de température" in ListLearnedSkillsTool(lab).run().text
    remove = RemoveLearnedSkillTool(lab, lambda names: [box.remove(n) for n in names])
    assert "supprimée" in remove.run("le convertisseur").text
    assert "celsius_to_fahrenheit" not in toolset.tool_names() and lab.installed() == []


def test_failing_tests_forbidden_code_and_network_are_refused(tmp_path):
    lab = Lab(tmp_path)
    wrong = TESTS.replace('"212 °F"', '"999 °F"')
    check = lab.check(draft(lab, "essai2", tests=wrong))
    assert not check.ok and check.failed == 1 and "1 test sur 3" in verdict(check)
    assert "Dis « réessaie »" in verdict(check)
    sneaky = lab.check(draft(lab, "essai3", skill=SKILL + "import os\n"))
    assert not sneaky.ok and sneaky.passed == 0  # refusée AVANT de lancer quoi que ce soit
    assert "son code fait des choses interdites" in verdict(sneaky)
    online = TESTS + "def test_web():\n    import httpx\n    httpx.get('https://example.com')\n"
    blocked = lab.check(draft(lab, "essai4", tests=online))
    assert not blocked.ok and blocked.failed == 1  # pas de réseau pendant les tests


def test_an_installed_skill_modified_later_is_not_loaded(tmp_path):
    lab = Lab(tmp_path)
    lab.install(lab.check(draft(lab, "essai5")))
    (folder,) = lab.installed()
    (folder / "skill.py").write_text(SKILL + "import subprocess\n", "utf-8")
    assert lab.load_all() == []  # ré-inspectée : refusée, Friday démarre quand même


def test_creating_a_skill_runs_claude_then_checks(tmp_path, monkeypatch):
    lab = Lab(tmp_path)
    done, finished = [], threading.Event()

    def fake_run(job, consigne, options=None):
        assert job.options == WRITER and "suivre mes colis" in consigne
        (job.workspace / "skill.py").write_text(SKILL, "utf-8")
        (job.workspace / "test_skill.py").write_text(TESTS, "utf-8")
        return {"ok": True, "result": "Compétence écrite.", "files": []}

    monkeypatch.setattr("friday.tools.claude_code.ClaudeCodeJob.run", fake_run)

    def on_done(task, result):
        done.append(result.text)
        finished.set()

    tool = CreateSkillTool(lab, "sonnet", 60, on_done)
    assert tool.needs_confirmation and "Je demande à Claude" in tool.confirmation(
        {"goal": "suivre mes colis"})  # fmt: skip
    assert tool.run("suivre mes colis").text.startswith("C'est lancé")
    assert finished.wait(120)
    assert done[0].startswith("Dis EXACTEMENT : « La compétence « Convertisseur")


def test_learned_skills_load_alongside_trading(tmp_path, monkeypatch):
    """Constaté (T8) : le labo des stratégies masquait l'atelier → démarrage impossible."""
    import dataclasses

    from fakes import SETTINGS

    from friday.tools import default_toolbox
    from friday.trading import Trading
    from friday.trading.context_builder import ContextBuilder
    from friday.trading.journal import TradeJournal
    from friday.trading.mode import TradingMode

    monkeypatch.setattr("friday.core.config.DATA_DIR", tmp_path)
    lab = Lab(tmp_path)
    lab.install(lab.check(draft(lab, "essai6")))
    journal = TradeJournal(tmp_path / "t.db")
    trading = Trading(TradingMode(), journal, ContextBuilder(None, journal), None, choice=object())
    claude = dataclasses.replace(SETTINGS, claude_enabled=True, claude_workspace=tmp_path)
    box = default_toolbox(claude, trading=trading, on_background=lambda *a: None)
    assert box.find("celsius_to_fahrenheit") is not None
    assert box.find("compare_strategies") is not None and box.find("log_trade") is not None
    assert box.find("trading_analysis") is None  # sans Claude : pas d'analyse
