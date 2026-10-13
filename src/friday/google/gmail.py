"""Gmail : lire (non lus, recherche, un mail) et envoyer. Aucune suppression possible
(les autorisations demandées ne le permettent même pas)."""

import base64
import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

MAX_BODY = 6000
SKIPPED_TABS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"}  # bruit pour un résumé
SCAN = 30  # mails examinés au plus pour en trouver assez hors promotions


@dataclass
class Mail:
    id: str
    thread_id: str
    sender: str  # « Julie Martin <julie@exemple.fr> »
    subject: str
    date: str
    snippet: str
    message_id: str = ""  # en-tête Message-ID (pour répondre dans la même conversation)
    body: str = ""
    labels: frozenset = frozenset()

    @property
    def unread(self) -> bool:
        return "UNREAD" in self.labels

    @property
    def sender_name(self) -> str:
        name, address = parseaddr(self.sender)
        return name or address


def _headers(payload: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style).*?</\1>", "", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", "", markup))
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def extract_body(payload: dict) -> str:
    """Texte d'un mail : la partie texte brut, sinon le HTML débarrassé des balises."""
    plain, rich = [], []

    def walk(part: dict) -> None:
        data = part.get("body", {}).get("data")
        mime = part.get("mimeType", "")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            rich.append(_decode(data))
        for child in part.get("parts", []):
            walk(child)

    walk(payload)
    text = "\n".join(plain).strip() or html_to_text("\n".join(rich))
    return text[:MAX_BODY]


def parse_mail(message: dict, with_body: bool = False) -> Mail:
    payload = message.get("payload", {})
    headers = _headers(payload)
    try:
        when = parsedate_to_datetime(headers.get("date", "")).astimezone().strftime("%d/%m %H:%M")
    except (TypeError, ValueError):
        when = ""
    return Mail(
        id=message["id"],
        thread_id=message.get("threadId", ""),
        sender=headers.get("from", ""),
        subject=headers.get("subject", "(sans objet)"),
        date=when,
        snippet=html.unescape(message.get("snippet", "")),
        message_id=headers.get("message-id", ""),
        body=extract_body(payload) if with_body else "",
        labels=frozenset(message.get("labelIds", [])),
    )


class Gmail:
    def __init__(self, service: Callable[[], object]) -> None:
        self._service = service
        self._address: str | None = None

    def address(self) -> str:
        """L'adresse du compte connecté à Friday ("" si inconnue), demandée une fois."""
        if self._address is None:
            try:
                profile = self._service().users().getProfile(userId="me").execute()
                self._address = profile.get("emailAddress", "")
            except Exception:
                return ""
        return self._address

    def link(self, mail_id: str) -> str:
        """Le mail dans Gmail, dans le BON compte. Constaté : avec deux comptes Google ouverts
        dans le navigateur, « /u/0/ » ouvrait celui qui n'est pas relié à Friday."""
        return f"https://mail.google.com/mail/u/{self.address() or 0}/#all/{mail_id}"

    def _messages(self):
        return self._service().users().messages()

    def _metadata(self, mail_id: str) -> Mail:
        return parse_mail(self._messages().get(
            userId="me", id=mail_id, format="metadata",
            metadataHeaders=["From", "Subject", "Date", "Message-ID"],
        ).execute())  # fmt: skip

    def search(self, query: str, limit: int = 8) -> list[Mail]:
        """Recherche Gmail (« from:julie », « facture »…)."""
        found = self._messages().list(userId="me", q=query, maxResults=limit).execute()
        return [self._metadata(m["id"]) for m in found.get("messages", [])]

    def unread(self, limit: int = 8, skip_tabs: bool = True) -> list[Mail]:
        return self.latest(limit, only_unread=True, skip_tabs=skip_tabs)

    def unread_total(self) -> int | None:
        """Nombre de non lus dans la boîte de réception, tous onglets (None : inconnu)."""
        try:
            label = self._service().users().labels().get(userId="me", id="INBOX").execute()
            return int(label.get("messagesUnread", 0))
        except Exception:
            return None

    def latest(self, limit: int = 5, only_unread: bool = False,
               skip_tabs: bool = True) -> list[Mail]:  # fmt: skip
        """Derniers mails de la boîte de réception, sans promotions ni réseaux sociaux (sauf
        `skip_tabs=False` : « ai-je des nouveaux mails ? » veut TOUS les non lus).

        Le tri se fait ici, sur les étiquettes de chaque mail : les filtres de recherche par
        onglet (« category:primary ») ne marchent pas sur tous les comptes."""
        query = "in:inbox is:unread" if only_unread else "in:inbox"
        found = self._messages().list(userId="me", q=query, maxResults=max(SCAN, limit)).execute()
        skipped = SKIPPED_TABS if skip_tabs else frozenset()
        mails = []
        for item in found.get("messages", []):
            mail = self._metadata(item["id"])
            if not mail.labels & skipped:
                mails.append(mail)
                if len(mails) >= limit:
                    break
        return mails

    def read(self, mail_id: str) -> Mail:
        return parse_mail(self._messages().get(userId="me", id=mail_id, format="full").execute(),
                          with_body=True)  # fmt: skip

    def find_address(self, name: str) -> str | None:
        """Adresse d'un contact d'après les mails échangés (« Julie » → julie@…)."""
        wanted = name.strip().lower()
        for mail in self.search(f"from:{wanted} OR to:{wanted}", limit=5):
            for display, address in getaddresses([mail.sender]):
                if wanted in display.lower() or wanted in address.lower():
                    return address
        return None

    def send(self, to: str, subject: str, body: str, reply_to: Mail | None = None) -> str:
        message = EmailMessage()
        message["To"], message["Subject"] = to, subject
        if reply_to and reply_to.message_id:  # même conversation chez le destinataire
            message["In-Reply-To"] = message["References"] = reply_to.message_id
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        payload = {"raw": raw, **({"threadId": reply_to.thread_id} if reply_to else {})}
        return self._messages().send(userId="me", body=payload).execute()["id"]
