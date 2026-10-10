"""Le contrat d'une compétence écrite par Claude (J8) : ce qu'on lui demande d'écrire, et les
droits avec lesquels il travaille (écrire des fichiers dans un dossier dédié, rien d'autre :
ni commande, ni internet, ni le reste du disque)."""

# Claude Code : uniquement lire / écrire / modifier des fichiers, confinés au dossier de travail
WRITER = ("--restricted", "--tools", "Read,Write,Edit", "--strict-mcp-config",
          "--no-session-persistence", "--permission-mode", "acceptEdits")  # fmt: skip

RULES = """Tu écris une nouvelle compétence pour Friday, un assistant vocal en français (Python
3.12, modèle local qwen3:8b). Écris EXACTEMENT deux fichiers dans le dossier courant :

1. skill.py — la compétence :
   from friday.tools.base import Tool, ToolResult
   SKILL = {"nom": "Suivi de colis", "resume": "une phrase", "mots_cles": ["colis", "suivi"],
            "exemples": ["où en est mon colis 1Z999", "suis le colis …"]}
   class TrackParcelTool(Tool):
       name = "track_parcel"            # snake_case, unique
       description = "Quand l'utiliser, en français, précis (le modèle choisit avec ça)."
       parameters = {"number": {"type": "string", "description": "…"}}
       required = ("number",)
       def __init__(self, client=None):  # AUCUN argument obligatoire
           self.client = client          # pour internet : httpx.Client(timeout=10) par défaut
       def label(self, args: dict) -> str: return "📦 Colis : …"
       def run(self, number: str) -> ToolResult:
           return ToolResult("Le texte que le modèle lira pour répondre (faits, chiffres).")
   - Un à trois outils au plus. Jamais d'exception non rattrapée : en cas d'erreur, renvoie
     un ToolResult qui explique simplement le problème.
   - Si la phrase à dire est connue d'avance, renvoie "Dis EXACTEMENT : « … »".
   - ToolResult est une dataclass : ToolResult(text: str) ; son texte se lit avec .text.

2. test_skill.py — des tests pytest (au moins 3) qui importent `from skill import …` et
   vérifient le comportement SANS internet : donne au constructeur un faux client (une petite
   classe dont .get() renvoie un objet avec .status_code, .json(), .text,
   .raise_for_status()). Les tests tournent sans réseau : un vrai appel échouerait.

Imports AUTORISÉS, et seulement eux : friday.tools.base, httpx (internet), json, re, math,
datetime, time, statistics, random, string, textwrap, html, unicodedata, dataclasses,
collections, itertools, functools, typing, enum, decimal, urllib.parse, zoneinfo (et pytest,
unittest.mock dans les tests). INTERDITS : os, sys, subprocess, pathlib, shutil, socket,
open(), eval, exec, __import__, getattr/setattr, les attributs en __double__, l'accès aux
fichiers. Pas de clé d'API ni de compte : seulement des services gratuits et sans clé.
Ne lis aucun autre fichier, n'écris rien d'autre. Termine par une phrase en français qui dit
ce que fait la compétence."""


def task(goal: str, previous_errors: str = "") -> str:
    """La consigne envoyée à Claude pour cette compétence."""
    text = f"Écris la compétence suivante pour Friday : {goal.strip()}"
    if previous_errors:
        text += ("\n\nUn premier essai a été refusé pour ces raisons ; corrige-les :\n"
                 + previous_errors[:3000])  # fmt: skip
    return text
