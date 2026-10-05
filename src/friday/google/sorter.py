"""Tri des mails par type : qwen3 classe chaque mail (expéditeur, sujet, extrait), Friday pose
l'étiquette « Friday/<catégorie> ». Rien n'est enlevé de la boîte de réception."""

import json
import logging
from collections import Counter
from collections.abc import Callable

from friday.google.gmail import Mail
from friday.google.mailbox import PREFIX, Mailbox

log = logging.getLogger(__name__)

CATEGORIES = (
    "Banque & finances", "Trading & crypto", "Achats & commandes", "Factures & abonnements",
    "Jeux", "IA & tech", "Travail & études", "Administratif", "Comptes & sécurité",
    "Voyages & transports", "Sport & santé", "Loisirs & culture", "Réseaux sociaux",
    "Personnel", "Autres",
)  # fmt: skip
CHUNK = 20  # mails classés par appel au modèle

PROMPT = """Range chaque mail dans UNE catégorie selon son THÈME (son sujet), d'après
l'expéditeur, le sujet et l'extrait, même quand c'est une publicité ou une newsletter :
une pub de jeu (RollerCoin, FDJ…) → « Jeux » ; une newsletter de trading, de bourse ou de
crypto (Bitget, Apex Trader…) → « Trading & crypto » ; une lettre sur l'IA, le code ou un
logiciel → « IA & tech » ; relevé, virement, carte → « Banque & finances » ; commande,
livraison, colis → « Achats & commandes » ; code de connexion, mot de passe, alerte de
sécurité → « Comptes & sécurité » ; impôts, CAF, assurance, mutuelle → « Administratif ».
« Autres » seulement si aucun thème ne convient.
Catégories possibles : {categories}.

Mails :
{mails}"""


def mail_summary(index: int, mail: Mail) -> str:
    tab = next((label.removeprefix("CATEGORY_").lower() for label in mail.labels
                if label.startswith("CATEGORY_")), "")  # fmt: skip
    hint = f" [onglet Gmail : {tab}]" if tab else ""
    return f"{index}. De : {mail.sender} — Sujet : {mail.subject} — {mail.snippet[:120]}{hint}"


class Classifier:
    """Appelle le modèle local avec une sortie JSON imposée (catégories en liste fermée)."""

    def __init__(self, client, model: str, num_ctx: int) -> None:
        self.client, self.model, self.num_ctx = client, model, num_ctx

    def __call__(self, mails: list[Mail], extra: tuple[str, ...] = ()) -> list[str]:
        """`extra` : catégories ajoutées par l'utilisateur (étiquettes « Friday/… »)."""
        categories = list(CATEGORIES) + [c for c in extra if c not in CATEGORIES]
        schema = {
            "type": "object",
            "properties": {"categories": {"type": "array", "items": {"enum": categories}}},
            "required": ["categories"],
        }
        lines = "\n".join(mail_summary(i, m) for i, m in enumerate(mails, 1))
        prompt = PROMPT.format(categories=", ".join(categories), mails=lines)
        prompt += f"\n\nRéponds avec exactement {len(mails)} catégories, dans l'ordre des mails."
        response = self.client.chat(
            model=self.model, messages=[{"role": "user", "content": prompt}], format=schema,
            think=False, keep_alive="30m", options={"num_ctx": self.num_ctx, "temperature": 0},
        )  # fmt: skip
        try:
            found = json.loads(response.message.content)["categories"]
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("Classement illisible : %r", response.message.content)
            found = []
        found = [c if c in categories else "Autres" for c in found]
        return (found + ["Autres"] * len(mails))[: len(mails)]


class MailSorter:
    def __init__(self, mailbox: Mailbox, classify: Callable[..., list[str]]) -> None:
        self.mailbox = mailbox
        self.classify = classify

    def sort_inbox(self, count: int) -> Counter:
        """Classe les `count` derniers mails de la boîte pas encore triés ; renvoie le compte
        par catégorie."""
        existing = self.mailbox.category_labels()
        already = set(existing.values())
        custom = tuple(name for name in existing if name not in CATEGORIES)
        mails = [m for m in self.mailbox.metadata(self.mailbox.ids("in:inbox", limit=count))
                 if not m.labels & already]  # fmt: skip
        by_category: dict[str, list[str]] = {}
        for start in range(0, len(mails), CHUNK):
            chunk = mails[start : start + CHUNK]
            for mail, category in zip(chunk, self.classify(chunk, custom), strict=True):
                by_category.setdefault(category, []).append(mail.id)
        for category, ids in by_category.items():
            self.mailbox.add_label(ids, self.mailbox.ensure_label(category))
        log.info("Tri de %d mails : %s", len(mails), {c: len(i) for c, i in by_category.items()})
        return Counter({category: len(ids) for category, ids in by_category.items()})


def find_category(said: str, known: list[str]) -> str | None:
    """« banque » → « Banque & finances » (parmi les catégories existantes)."""
    from friday.voice.wake import normalize

    wanted = normalize(said.removeprefix(PREFIX))
    if not wanted:
        return None
    for name in known:
        if normalize(name) == wanted:
            return name
    words = [w for w in wanted.split() if w not in {"de", "des", "du", "la", "le", "les", "et"}]

    def singular(word: str) -> str:  # « banques » → « banque », « jeux » → « jeu »
        return word[:-1] if len(word) > 3 and word[-1] in "sx" else word

    matches = [n for n in known if all(singular(w) in normalize(n) for w in words)]
    return matches[0] if len(matches) == 1 else None
