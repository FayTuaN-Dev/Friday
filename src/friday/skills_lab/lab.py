"""L'atelier de compétences (J8) : un essai écrit par Claude (data/atelier/<date>/) est
inspecté puis testé À PART (autre processus, sans réseau, 90 s au plus) ; il n'est installé
(data/competences/<nom>/) qu'avec l'accord de l'utilisateur, et ré-inspecté à chaque
chargement. Aucune compétence ne s'installe ni ne se charge si l'inspection échoue."""

import importlib.util
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from friday.skills_lab.inspection import Inspection, inspect_skill
from friday.tools.base import Tool

log = logging.getLogger(__name__)

SRC = Path(__file__).resolve().parents[2]  # le dossier « src » de Friday
TEST_TIMEOUT = 90
MAX_INSTALLED = 8  # au-delà, trop d'outils toujours présentés au modèle
# Pendant les tests : toute connexion réseau échoue (les tests ne doivent pas en dépendre)
NO_NETWORK = """import socket
def _blocked(*args, **kwargs):
    raise OSError("réseau coupé pendant les tests de la compétence")
socket.socket.connect = _blocked
socket.create_connection = _blocked
"""


@dataclass
class Check:
    folder: Path
    info: dict = field(default_factory=dict)  # la fiche SKILL
    inspection: Inspection = field(default_factory=Inspection)
    passed: int = 0
    failed: int = 0
    output: str = ""  # sortie des tests (pour corriger)

    @property
    def ok(self) -> bool:
        return self.inspection.ok and self.passed > 0 and self.failed == 0

    @property
    def name(self) -> str:
        return str(self.info.get("nom") or self.folder.name)

    def problems(self) -> str:
        if not self.inspection.ok:
            return "\n".join(self.inspection.problems)
        return self.output[-3000:] if not self.ok else ""


def slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40] or "competence"


def load_module(folder: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, folder / "skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tools_of(module) -> list[Tool]:
    own = [obj for obj in vars(module).values() if isinstance(obj, type) and issubclass(obj, Tool)]
    return [obj() for obj in own if obj is not Tool and obj.__module__ == module.__name__]


class Lab:
    def __init__(self, data_dir: Path) -> None:
        self.drafts = data_dir / "atelier"  # les essais de Claude
        self.installed_dir = data_dir / "competences"
        self.last: Check | None = None  # dernier essai vérifié (à installer, ou à corriger)

    def new_draft(self, stamp: str) -> Path:
        folder = self.drafts / stamp
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def inspect(self, folder: Path) -> Inspection:
        try:
            skill = (folder / "skill.py").read_text("utf-8")
            tests = (folder / "test_skill.py").read_text("utf-8")
        except OSError:
            return Inspection(["skill.py ou test_skill.py manquant"])
        return inspect_skill(skill, tests)

    def check(self, folder: Path) -> Check:
        """Inspecte, puis (seulement si l'inspection passe) lance les tests à part."""
        check = Check(folder, inspection=self.inspect(folder))
        if check.inspection.ok:
            self._run_tests(check)
            if check.ok:
                check.info = dict(getattr(load_module(folder, f"friday_draft_{folder.name}"),
                                          "SKILL", {}) or {})  # fmt: skip
        self.last = check
        log.info("Atelier : %s → %s (%d/%d tests)", folder.name, "OK" if check.ok else "refusé",
                 check.passed, check.passed + check.failed)  # fmt: skip
        return check

    def _run_tests(self, check: Check) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp)
            for name in ("skill.py", "test_skill.py"):
                shutil.copy2(check.folder / name, sandbox / name)
            (sandbox / "conftest.py").write_text(NO_NETWORK, "utf-8")
            env = {"PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8",
                   "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}  # fmt: skip
            try:
                run = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                    cwd=sandbox, env=env, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=TEST_TIMEOUT)  # fmt: skip
                check.output = run.stdout + run.stderr
            except subprocess.TimeoutExpired:
                check.output = f"Les tests n'ont pas fini en {TEST_TIMEOUT} s."
        check.passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", check.output)) else 0
        check.failed = sum(int(n) for n in re.findall(r"(\d+) (?:failed|error)", check.output))

    # --- Compétences installées ---

    def installed(self) -> list[Path]:
        if not self.installed_dir.is_dir():
            return []
        return sorted(p for p in self.installed_dir.iterdir() if (p / "skill.py").is_file())

    def install(self, check: Check) -> Path:
        if not check.ok:
            raise ValueError("cette compétence n'a pas passé l'inspection et les tests")
        if len(self.installed()) >= MAX_INSTALLED:
            raise ValueError(f"déjà {MAX_INSTALLED} compétences : supprimes-en une d'abord")
        target = self.installed_dir / slug(check.name)
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for name in ("skill.py", "test_skill.py"):
            shutil.copy2(check.folder / name, target / name)
        return target

    def load(self, folder: Path) -> tuple[dict, list[Tool]]:
        """Ré-inspectée à chaque chargement : un fichier modifié depuis n'est pas chargé."""
        inspection = self.inspect(folder)
        if not inspection.ok:
            raise ValueError("inspection refusée : " + "; ".join(inspection.problems[:3]))
        module = load_module(folder, f"friday_skill_{folder.name.replace('-', '_')}")
        return dict(getattr(module, "SKILL", {}) or {}), tools_of(module)

    def load_all(self) -> list[tuple[Path, dict, list[Tool]]]:
        loaded = []
        for folder in self.installed():
            try:
                info, tools = self.load(folder)
                loaded.append((folder, info, tools))
            except Exception as error:  # une compétence cassée ne doit pas bloquer Friday
                log.warning("Compétence « %s » non chargée : %s", folder.name, error)
        return loaded

    def remove(self, folder: Path) -> None:
        shutil.rmtree(folder, ignore_errors=True)
