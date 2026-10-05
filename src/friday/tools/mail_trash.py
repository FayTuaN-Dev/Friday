"""Outil : mettre des mails à la corbeille (récupérables 30 jours), TOUJOURS après une
confirmation qui donne le nombre de mails et des exemples ; seuls ces mails-là sont touchés."""

from friday.google.mailbox import Mailbox
from friday.google.sorter import find_category
from friday.tools.base import Tool, ToolResult
from friday.tools.google_base import guarded

FIELDS = ("categories", "except_categories", "query", "mail_id")


def split_names(value) -> list[str]:
    """« Jeux, Trading & crypto » ou ["Jeux", …] → liste de noms."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value or "").replace(";", ",").split(",") if part.strip()]


class TrashMailsTool(Tool):
    name = "trash_mails"
    description = (
        "Met des mails à la corbeille (récupérables 30 jours), après confirmation. Au choix : "
        "categories (une ou plusieurs catégories du tri : « Jeux, Trading & crypto ») ; "
        "except_categories (toutes les catégories SAUF celles-ci : « supprime tout sauf "
        "Administratif et Factures ») ; query (expéditeur ou mots : « from:rollercoin ») ; "
        "mail_id (un mail précis)."
    )
    parameters = {
        "categories": {"type": "string", "description": "Catégories à vider (virgules)"},
        "except_categories": {"type": "string", "description": "Catégories à GARDER"},
        "query": {"type": "string", "description": "Recherche Gmail : from:nom, mots"},
        "mail_id": {"type": "string", "description": "Identifiant d'un mail précis"},
    }
    needs_confirmation = True
    timeout = 300  # des centaines de mails

    def __init__(self, mailbox: Mailbox) -> None:
        self.mailbox = mailbox
        self._pending: tuple | None = None  # (demande, identifiants) confirmés

    def label(self, args: dict) -> str:
        return "🗑️ Corbeille"

    def _resolve(self, names: list[str], labels: dict[str, str]) -> list[str]:
        resolved = []
        for said in names:
            name = find_category(said, list(labels))
            if name is None:
                known = ", ".join(sorted(labels)) or "aucune (trie d'abord les mails)"
                raise LookupError(f"catégorie « {said} » inconnue (existantes : {known})")
            resolved.append(name)
        return resolved

    def _select(self, args: dict) -> tuple[str, list[str]]:
        if args.get("mail_id"):
            return "ce mail", [args["mail_id"]]
        wanted, kept = (
            split_names(args.get("categories")),
            split_names(args.get("except_categories")),
        )
        if wanted or kept:
            labels = self.mailbox.category_labels()
            if kept:
                kept_names = set(self._resolve(kept, labels))
                names = [n for n in labels if n not in kept_names]
            else:
                names = self._resolve(wanted, labels)
            ids = list(
                dict.fromkeys(i for n in names for i in self.mailbox.ids("-in:trash", labels[n]))
            )
            return "des catégories " + ", ".join(f"« {n} »" for n in names), ids
        query = (args.get("query") or "").strip()
        if "category:" in query or "label:" in query:  # syntaxe inventée par le modèle
            raise LookupError("pour des catégories, utilise categories ou except_categories, "
                              "pas query")  # fmt: skip
        if not query:
            raise LookupError("il faut des catégories, une recherche ou un mail précis")
        return f"pour « {query} »", self.mailbox.ids(f"{query} -in:trash")

    @staticmethod
    def _request(args: dict) -> dict:
        return {k: args[k] for k in FIELDS if args.get(k)}

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
        self._pending = (self._request(args), ids)
        return f"Je mets {len(ids)} mail(s) {what} à la corbeille ? Par exemple : {examples}."

    def run(self, categories="", except_categories="", query: str = "",
            mail_id: str = "") -> ToolResult:  # fmt: skip
        args = self._request({"categories": categories, "except_categories": except_categories,
                              "query": query, "mail_id": mail_id})  # fmt: skip
        pending, self._pending = self._pending, None
        if pending is None or pending[0] != args:
            try:
                what, ids = self._select(args)
            except Exception as error:
                return ToolResult(f"Rien supprimé : {error}. Explique-le, ou réessaie autrement.")
            return ToolResult(f"Rien supprimé : aucun mail {what}." if not ids else
                              "Rien supprimé : la suppression n'a pas été confirmée.")  # fmt: skip

        def trash() -> ToolResult:
            done = self.mailbox.trash(pending[1])
            return ToolResult(
                f"{done} mail(s) mis à la corbeille (récupérables 30 jours dans Gmail). "
                "Confirme-le en une phrase."
            )

        return guarded(trash)
