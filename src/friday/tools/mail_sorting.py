"""Outils : trier les mails par thème, voir une catégorie (corbeille : mail_trash.py)."""

import threading

from friday.google.mailbox import Mailbox
from friday.google.sorter import MailSorter, find_category
from friday.tools.base import Display, Tool, ToolResult
from friday.tools.gmail import mail_list
from friday.tools.google_base import guarded

IN_FOREGROUND = 100  # au-delà, tri en arrière-plan (environ 3 s pour 10 mails)
MAX_ALL = 3000  # « tous » : plafond de sécurité


class SortMailsTool(Tool):
    name = "sort_mails"
    description = (
        "Trie les mails de la boîte de réception par thème (jeux, trading, banque, achats…) en "
        "leur posant une étiquette « Friday/… » visible dans Gmail ; ne supprime et ne déplace "
        "rien. count : nombre de derniers mails (50 par défaut), ou 0 pour TOUS (« range tous "
        "mes mails ») : le tri se fait alors en arrière-plan."
    )
    parameters = {"count": {"type": "integer", "description": "50 par défaut ; 0 = tous"}}
    timeout = 300  # lecture des mails + classement par le modèle

    def __init__(self, sorter: MailSorter, on_background=None) -> None:
        self.sorter = sorter
        self.on_background = on_background  # (tâche, résultat) : annonce de fin de tri

    def label(self, args: dict) -> str:
        return "🗂️ Tri des mails"

    def run(self, count: int | None = None) -> ToolResult:
        count = MAX_ALL if count == 0 else int(count or 50)
        if count > IN_FOREGROUND and self.on_background is not None:
            threading.Thread(target=self._sort_in_background, args=(count,), daemon=True,
                             name="mail-sort").start()  # fmt: skip
            return ToolResult(
                "C'est lancé : je trie tous les mails en arrière-plan (plusieurs minutes, environ "
                "3 secondes pour 10 mails) et je préviendrai à la fin. Dis-le en une phrase."
            )
        return guarded(lambda: self._sort(min(count, IN_FOREGROUND)))

    def _sort(self, count: int) -> ToolResult:
        counts = self.sorter.sort_inbox(count)
        if not counts:
            return ToolResult("Rien à trier : ces mails sont déjà rangés.")
        ranked = counts.most_common()
        summary = ", ".join(f"{name} : {n}" for name, n in ranked)
        items = [{"text": name, "meta": f"{n} mail(s)"} for name, n in ranked]
        return ToolResult(
            f"{sum(counts.values())} mails triés. Par catégorie : {summary}. Dis le total "
            "et les deux ou trois plus grosses catégories ; le détail est à l'écran.",
            Display("items", "Mails triés", {"icon": "🗂️", "items": items}),
        )

    def _sort_in_background(self, count: int) -> None:
        result = guarded(lambda: self._sort(count))
        self.on_background("tri des mails", ToolResult(
            f"Le tri des mails en arrière-plan est terminé. {result.text}", result.display
        ))  # fmt: skip


# « Quelles catégories ai-je ? » : reconnu par le code (le modèle se trompait 3 fois sur 8)
ASKS = ("quelles categories", "quelle categorie", "mes categories", "liste des categories",
        "categories de mail", "categories de courriel", "categories existent")  # fmt: skip


def asks_categories(text: str) -> bool:
    from friday.voice.wake import normalize

    padded = f" {normalize(text)} "
    return any(f" {words}" in padded for words in ASKS)


def say_list(names: list[str]) -> str:
    names = sorted(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " et " + names[-1]


def categories_context(mailbox: Mailbox) -> str:
    """La VRAIE liste des catégories, donnée au modèle dès qu'on parle de mails."""
    try:
        names = list(mailbox.category_labels())
    except Exception:  # Gmail pas encore connecté : rien plutôt qu'une erreur
        return ""
    if not names:
        return "Catégories de mails : aucune pour l'instant (les mails n'ont pas été triés)."
    return (f"Catégories de mails existantes (tri de Friday) : {say_list(names)}. N'en cite "
            "aucune autre.")  # fmt: skip


class CategoryMailsTool(Tool):
    name = "category_mails"
    description = (
        "Montre les mails d'une catégorie créée par le tri (« mes mails de banque »), ou la "
        "liste des catégories si aucune n'est donnée."
    )
    parameters = {
        "category": {"type": "string", "description": "La catégorie (banque, promotions…)"},
        "count": {"type": "integer", "description": "Combien de mails (10 par défaut)"},
    }

    def __init__(self, mailbox: Mailbox) -> None:
        self.mailbox = mailbox

    def label(self, args: dict) -> str:
        return f"🗂️ Catégorie : {args.get('category') or 'toutes'}"

    def run(self, category: str = "", count: int | None = None) -> ToolResult:
        def show() -> ToolResult:
            labels = self.mailbox.category_labels()
            if not labels:
                return ToolResult("Dis EXACTEMENT : « Aucune catégorie : tes mails n'ont pas "
                                  "encore été triés. Dis « trie mes mails ». »")  # fmt: skip
            name = find_category(category, list(labels)) if category else None
            if name is None:
                unknown = f"Je n'ai pas de catégorie « {category} ». " if category else ""
                return ToolResult(f"Dis EXACTEMENT : « {unknown}Tes catégories de mails : "
                                  f"{say_list(list(labels))}. »")  # fmt: skip
            ids = self.mailbox.ids(
                "-in:trash", labels[name], limit=max(1, min(int(count or 10), 30))
            )
            if not ids:
                return ToolResult(f"Plus aucun mail dans « {name} ».")
            return mail_list(self.mailbox.metadata(ids), f"Mails « {name} »")

        return guarded(show)
