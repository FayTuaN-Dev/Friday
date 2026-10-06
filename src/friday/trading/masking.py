"""Masquage des données sensibles AVANT l'aperçu d'un envoi à Claude.

Deux niveaux :
- `mask_secrets` : ce qui ne doit jamais partir, où que ce soit (e-mails, IBAN, numéros de
  compte ou de carte, clés et jetons d'API, chemins de fichiers, mots de la liste de blocage).
- `mask_personal` : en plus, les montants d'argent (solde, capital…). Appliqué au texte de
  l'utilisateur ; pas aux extraits de livres, dont les exemples chiffrés sont utiles.

Une image ne peut pas être masquée ainsi : d'où la capture limitée à une zone (PR suivante)
et l'aperçu obligatoire, où l'utilisateur voit ce qui part.
"""

import re
from dataclasses import dataclass, field

_SECRETS = (
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?\b")),
    ("clé", re.compile(r"\b(?:sk|pk|rk|api|key|token|secret)[-_][A-Za-z0-9_-]{12,}\b", re.I)),
    ("clé", re.compile(r"\b(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{32,}\b")),
    ("chemin", re.compile(r"\b[A-Za-z]:\\[^\s\"'<>|]+|(?:/Users|/home)/[^\s\"'<>|]+")),
    # 8 chiffres ou plus (espaces et tirets admis) : numéro de compte, de carte, de client
    # (une virgule ou un point de ponctuation autour ne compte pas : seulement « 1,5 » décimal)
    ("numéro", re.compile(r"(?<!\d)(?<!\d[.,])\d(?:[ -]?\d){7,}(?!\d|[.,]\d)")),
)  # fmt: skip
_CURRENCY = r"(?:€|euros?|eur|\$|usd|dollars?|£|gbp|chf|francs?)"
_AMOUNT = re.compile(rf"(?:{_CURRENCY}\s?\d[\d\s.,]*\d|\d[\d\s.,]*\s?{_CURRENCY})(?![a-z])", re.I)
_K_AMOUNT = re.compile(rf"\b\d+(?:[.,]\d+)?\s?k\s?{_CURRENCY}?(?![a-z])", re.I)  # « 5k »


@dataclass
class Masked:
    text: str
    found: list[str] = field(default_factory=list)  # ce qui a été masqué (types), pour l'aperçu


def _apply(text: str, kind: str, pattern: re.Pattern, found: list[str]) -> str:
    def replace(match: re.Match) -> str:
        found.append(kind)
        return f"[{kind} masqué]"

    return pattern.sub(replace, text)


def mask_secrets(text: str, blocklist: tuple[str, ...] = ()) -> Masked:
    found: list[str] = []
    for word in blocklist:
        if word.strip():
            text = _apply(text, "donnée", re.compile(re.escape(word.strip()), re.I), found)
    for kind, pattern in _SECRETS:
        text = _apply(text, kind, pattern, found)
    return Masked(text, found)


def mask_personal(text: str, blocklist: tuple[str, ...] = ()) -> Masked:
    masked = mask_secrets(text, blocklist)
    text = _apply(masked.text, "montant", _AMOUNT, masked.found)
    text = _apply(text, "montant", _K_AMOUNT, masked.found)
    return Masked(text, masked.found)
