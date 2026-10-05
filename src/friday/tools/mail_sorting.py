"""Outils : trier les mails par catégorie, voir une catégorie, mettre à la corbeille
(toujours après confirmation, avec le nombre de mails et des exemples)."""

from friday.google.mailbox import Mailbox
from friday.google.sorter import MailSorter, find_category
from friday.tools.base import Display, Tool, ToolResult
from friday.tools.gmail import mail_list
from friday.tools.google_base import guarded


class SortMailsTool(Tool):
    name = "sort_mails"
    description = (
        "Trie les derniers mails de la boîte de réception par catégorie (banque, achats, "
        "promotions, jeux…) en leur posant une étiquette « Friday/… » visible dans Gmail. "
        "Ne supprime et ne déplace rien."
    )
    parameters = {"count": {"type": "integer", "description": "Combien de mails (50 par défaut)"}}
    timeout = 300  # lecture des mails + classement par le modèle

    def __init__(self, sorter: MailSorter) -> None:
        self.sorter = sorter

    def label(self, args: dict) -> str:
        return "🗂️ Tri des mails"

    def run(self, count: int | None = None) -> ToolResult:
        def sort() -> ToolResult:
            counts = self.sorter.sort_inbox(max(1, min(int(count or 50), 200)))
            if not counts:
                return ToolResult("Rien à trier : les derniers mails sont déjà rangés.")
            ranked = counts.most_common()
            summary = ", ".join(f"{name} : {n}" for name, n in ranked)
            items = [{"text": name, "meta": f"{n} mail(s)"} for name, n in ranked]
            return ToolResult(
                f"{sum(counts.values())} mails triés. Par catégorie : {summary}. Dis le total "
                "et les deux ou trois plus grosses catégories ; le détail est à l'écran.",
                Display("items", "Mails triés", {"icon": "🗂️", "items": items}),
            )

        return guarded(sort)


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
                return ToolResult("Aucune catégorie : les mails n'ont pas encore été triés.")
            name = find_category(category, list(labels)) if category else None
            if name is None:
                known = ", ".join(sorted(labels))
                return ToolResult(f"Catégories existantes : {known}.")
            ids = self.mailbox.ids(
                "-in:trash", labels[name], limit=max(1, min(int(count or 10), 30))
            )
            if not ids:
                return ToolResult(f"Plus aucun mail dans « {name} ».")
            return mail_list(self.mailbox.metadata(ids), f"Mails « {name} »")

        return guarded(show)


class TrashMailsTool(Tool):
    name = "trash_mails"
    description = (
        "Met des mails à la corbeille (récupérables 30 jours), après confirmation : toute une "
        "catégorie (« supprime les promotions »), ceux d'un expéditeur ou d'une recherche "
        "(query : « from:rollercoin »), ou un mail précis (mail_id)."
    )
    parameters = {
        "category": {"type": "string", "description": "Catégorie du tri (promotions…)"},
        "query": {"type": "string", "description": "Recherche Gmail (from:nom, mots…)"},
        "mail_id": {"type": "string", "description": "Identifiant d'un mail précis"},
    }
    needs_confirmation = True

    def __init__(self, mailbox: Mailbox) -> None:
        self.mailbox = mailbox
        self._pending: tuple | None = None  # (arguments, identifiants) confirmés

    def label(self, args: dict) -> str:
        return "🗑️ Corbeille"

    def _select(self, args: dict) -> tuple[str, list[str]]:
        if args.get("mail_id"):
            return "ce mail", [args["mail_id"]]
        if args.get("category"):
            labels = self.mailbox.category_labels()
            name = find_category(args["category"], list(labels))
            if name is None:
                known = ", ".join(sorted(labels)) or "aucune"
                raise LookupError(
                    f"catégorie « {args['category']} » inconnue (existantes : {known})"
                )
            return f"de la catégorie « {name} »", self.mailbox.ids("-in:trash", labels[name])
        query = (args.get("query") or "").strip()
        if not query:
            raise LookupError("il faut une catégorie, une recherche ou un mail précis")
        return f"pour « {query} »", self.mailbox.ids(f"{query} -in:trash")

    def confirmation(self, args: dict) -> str | None:
        self._pending = None
        try:
            what, ids = self._select(args)
        except Exception:
            return None  # rien ne sera supprimé : run() explique pourquoi
        if not ids:
            return None
        samples = self.mailbox.metadata(ids[:3])
        examples = ", ".join(f"{m.sender_name} (« {m.subject[:40]} »)" for m in samples)
        self._pending = (dict(args), ids)
        return f"Je mets {len(ids)} mail(s) {what} à la corbeille ? Par exemple : {examples}."

    def run(self, category: str = "", query: str = "", mail_id: str = "") -> ToolResult:
        args = {k: v for k, v in (("category", category), ("query", query),
                                  ("mail_id", mail_id)) if v}  # fmt: skip
        pending, self._pending = self._pending, None
        if pending is None or {k: v for k, v in pending[0].items() if v} != args:
            try:
                what, ids = self._select(args)
            except Exception as error:
                return ToolResult(f"Rien supprimé : {error}. Explique-le à l'utilisateur.")
            return ToolResult(f"Rien supprimé : aucun mail {what}." if not ids else
                              "Rien supprimé : la suppression n'a pas été confirmée.")  # fmt: skip

        def trash() -> ToolResult:
            done = self.mailbox.trash(pending[1])
            return ToolResult(
                f"{done} mail(s) mis à la corbeille (récupérables 30 jours dans Gmail). "
                "Confirme-le en une phrase."
            )

        return guarded(trash)
