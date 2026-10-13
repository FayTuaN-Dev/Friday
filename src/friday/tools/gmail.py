"""Outils : Gmail (non lus, recherche, lecture, envoi TOUJOURS après confirmation)."""

from friday.google.gmail import Gmail, Mail
from friday.tools.base import Display, Tool, ToolResult
from friday.tools.google_base import guarded

GMAIL_URL = "https://mail.google.com/mail/u/0/#all/{id}"


def mail_list(mails: list[Mail], title: str) -> ToolResult:
    lines = [f"- [id : {m.id}] {m.date}{' (non lu)' if m.unread else ''} — {m.sender_name} : "
             f"« {m.subject} » — {m.snippet[:140]}"
             for m in mails]  # fmt: skip
    items = [{"text": m.subject, "meta": f"{m.sender_name} · {m.date}",
              "url": GMAIL_URL.format(id=m.id)} for m in mails]  # fmt: skip
    return ToolResult(
        f"{title} ({len(mails)}, affichés à l'écran) :\n"
        + "\n".join(lines)
        + "\nÀ l'oral : résume brièvement (expéditeurs et sujets importants), sans lire les "
        "identifiants ni les adresses. N'invente rien : dis seulement ce qui figure ci-dessus "
        "(l'extrait n'est que le début du mail).",
        Display("items", title, {"icon": "✉️", "items": items}),
    )


class CheckMailTool(Tool):
    name = "check_mail"
    description = (
        "Derniers mails reçus dans la boîte de réception : « mes 5 derniers mails », « ai-je "
        "de nouveaux mails ? » (only_unread=true pour les non lus seulement)."
    )
    parameters = {
        "count": {
            "type": "integer",
            "description": "Combien (5 par défaut, 10 pour les non lus, 25 au plus)",
        },
        "only_unread": {"type": "boolean", "description": "Seulement les non lus"},
    }

    def __init__(self, gmail: Gmail) -> None:
        self.gmail = gmail

    def label(self, args: dict) -> str:
        return "✉️ Mails non lus" if args.get("only_unread") else "✉️ Derniers mails"

    def run(self, count: int | None = None, only_unread: bool = False) -> ToolResult:
        def check() -> ToolResult:
            # Constaté : « que 5 mails non lus » alors qu'il y en avait 10 (promotions comprises)
            limit = max(1, min(int(count or (10 if only_unread else 5)), 25))
            mails = self.gmail.latest(limit, only_unread, skip_tabs=not only_unread)
            if not mails:
                return ToolResult(
                    "Aucun mail non lu." if only_unread else "Boîte de réception vide."
                )
            result = mail_list(mails, "Mails non lus" if only_unread else "Derniers mails reçus")
            total = self.gmail.unread_total() if only_unread else None
            if total and total > len(mails):
                result.text = (f"{total} mails non lus au total dans la boîte de réception : "
                               f"annonce ce total, voici les {len(mails)} plus récents.\n"
                               + result.text)  # fmt: skip
            return result

        return guarded(check)


class SearchMailTool(Tool):
    name = "search_mail"
    description = (
        "Cherche des mails (« le mail de la banque », « les mails de Julie »). La recherche "
        "accepte des mots, ou from:nom, subject:mot, newer_than:7d."
    )
    parameters = {"query": {"type": "string", "description": "Mots ou recherche Gmail"}}
    required = ("query",)

    def __init__(self, gmail: Gmail) -> None:
        self.gmail = gmail

    def label(self, args: dict) -> str:
        return f"✉️ Recherche : {args.get('query', '')}"

    def run(self, query: str) -> ToolResult:
        def search() -> ToolResult:
            mails = self.gmail.search(query)
            if not mails:
                return ToolResult(f"Aucun mail trouvé pour « {query} ».")
            return mail_list(mails, f"Mails : {query}")

        return guarded(search)


class ReadMailTool(Tool):
    name = "read_mail"
    description = "Lit un mail en entier (id donné par check_mail ou search_mail)."
    parameters = {"mail_id": {"type": "string", "description": "Identifiant du mail"}}
    required = ("mail_id",)

    def __init__(self, gmail: Gmail) -> None:
        self.gmail = gmail

    def label(self, args: dict) -> str:
        return "✉️ Lecture d'un mail"

    def run(self, mail_id: str) -> ToolResult:
        def read() -> ToolResult:
            mail = self.gmail.read(mail_id)
            text = f"De : {mail.sender}\nObjet : {mail.subject}\nDate : {mail.date}\n\n{mail.body}"
            return ToolResult(
                f"{text}\n\nRésume-le à l'oral, en t'en tenant strictement à ce qu'il dit (rien "
                "d'inventé ni d'interprété) ; le texte complet est affiché.",
                Display(
                    "article", mail.subject, {"url": GMAIL_URL.format(id=mail.id), "text": text}
                ),  # fmt: skip
            )

        return guarded(read)


class SendMailTool(Tool):
    name = "send_mail"
    description = (
        "Envoie un mail (ou répond à un mail : reply_to_id). L'utilisateur voit le brouillon et "
        "confirme avant tout envoi. « to » : une adresse, ou le nom d'un contact avec qui il a "
        "déjà échangé. Rédige un message complet, poli, signé du prénom de l'utilisateur si tu "
        "le connais."
    )
    parameters = {
        "to": {"type": "string", "description": "Adresse ou nom du destinataire"},
        "subject": {"type": "string", "description": "Objet (vide pour une réponse)"},
        "body": {"type": "string", "description": "Le message complet"},
        "reply_to_id": {"type": "string", "description": "Id du mail auquel on répond"},
    }
    required = ("body",)
    needs_confirmation = True  # jamais d'envoi sans « oui »

    def __init__(self, gmail: Gmail) -> None:
        self.gmail = gmail
        self._draft: tuple | None = None  # le brouillon exact qui a été montré et confirmé

    def label(self, args: dict) -> str:
        return "✉️ Envoi d'un mail"

    def _prepare(self, args: dict) -> tuple[str, str, str, Mail | None] | None:
        original = self.gmail.read(args["reply_to_id"]) if args.get("reply_to_id") else None
        to = (args.get("to") or (original.sender if original else "")).strip()
        if "@" not in to:
            to = self.gmail.find_address(to) or "" if to else ""
        if not to:
            return None
        subject = args.get("subject") or (f"Re: {original.subject}" if original else "(sans objet)")
        if original and not subject.lower().startswith("re:"):
            subject = f"Re: {original.subject}"
        return to, subject, args["body"].strip(), original

    def confirmation(self, args: dict) -> str | None:
        try:
            self._draft = self._prepare(args)
        except Exception:
            self._draft = None
        if self._draft is None:
            return None  # rien ne sera envoyé : run() explique pourquoi, sans question inutile
        to, subject, body, _ = self._draft
        return f"J'envoie ce mail à {to} ? Objet : {subject}. Message : « {body} »"

    def run(self, body: str, to: str = "", subject: str = "", reply_to_id: str = "") -> ToolResult:
        draft, self._draft = self._draft, None
        if draft is None or draft[2] != body.strip():
            return ToolResult(
                f"Mail NON envoyé : je ne trouve pas l'adresse de « {to} ». Demande-la à "
                "l'utilisateur (ou le nom exact d'un contact avec qui il a échangé)."
            )
        to, subject, body, original = draft

        def send() -> ToolResult:
            self.gmail.send(to, subject, body, reply_to=original)
            return ToolResult(f"Mail envoyé à {to}. Confirme-le en une phrase.")

        return guarded(send)
