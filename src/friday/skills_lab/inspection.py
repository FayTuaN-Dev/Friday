"""Inspection d'une compétence écrite par Claude (J8), AVANT de l'exécuter : le code est lu
(arbre syntaxique), jamais lancé. Refusé : un import hors liste, eval/exec/open…, tout
attribut en __double__ (porte de sortie classique). Les droits sont déduits du code : httpx
→ « internet ». C'est un garde-fou, pas une garantie : l'utilisateur valide en dernier."""

import ast
from dataclasses import dataclass, field

SAFE = {"json", "re", "math", "datetime", "time", "statistics", "random", "string", "textwrap",
        "html", "unicodedata", "dataclasses", "collections", "itertools", "functools",
        "typing", "enum", "decimal", "urllib.parse", "zoneinfo", "friday.tools.base",
        "__future__"}  # fmt: skip
NETWORK = {"httpx"}
TESTS_ONLY = {"pytest", "unittest.mock", "skill"}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "open", "input", "breakpoint",
                   "globals", "locals", "vars", "getattr", "setattr", "delattr", "exit",
                   "quit", "memoryview"}  # fmt: skip
ALLOWED_DUNDERS = {"__init__", "__name__", "__future__"}


@dataclass
class Inspection:
    problems: list[str] = field(default_factory=list)
    rights: set[str] = field(default_factory=set)  # « internet »

    @property
    def ok(self) -> bool:
        return not self.problems


def inspect_source(source: str, filename: str, tests: bool = False) -> Inspection:
    found = Inspection()
    try:
        tree = ast.parse(source, filename)
    except SyntaxError as error:
        found.problems.append(f"{filename} : erreur de syntaxe ligne {error.lineno}")
        return found
    allowed = SAFE | NETWORK | (TESTS_ONLY if tests else set())
    for node in ast.walk(tree):
        where = f"{filename}:{getattr(node, 'lineno', '?')}"
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""] if not node.level else ["(import relatif)"]
        for module in modules:
            if module not in allowed:
                found.problems.append(f"{where} : import interdit « {module} »")
            if module in NETWORK:
                found.rights.add("internet")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_CALLS:
            found.problems.append(f"{where} : « {node.id} » interdit")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__") and (
                node.attr not in ALLOWED_DUNDERS):  # fmt: skip
            found.problems.append(f"{where} : attribut « {node.attr} » interdit")
        if isinstance(node, ast.Name) and node.id.startswith("__") and (
                node.id not in ALLOWED_DUNDERS):  # fmt: skip
            found.problems.append(f"{where} : nom « {node.id} » interdit")
    return found


def inspect_skill(skill_source: str, tests_source: str) -> Inspection:
    """Les deux fichiers ; les droits sont ceux de la compétence (pas des tests)."""
    skill = inspect_source(skill_source, "skill.py")
    tests = inspect_source(tests_source, "test_skill.py", tests=True)
    if "SKILL" not in skill_source:
        skill.problems.append("skill.py : la fiche SKILL (nom, résumé, mots-clés) manque")
    return Inspection(skill.problems + tests.problems, skill.rights)
