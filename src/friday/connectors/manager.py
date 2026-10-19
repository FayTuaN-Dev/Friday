"""Les connecteurs de Friday : relit data/mcp.json, branche chaque serveur coché en arrière-plan
(un serveur lent ou en panne ne retarde ni ne bloque rien) et donne ses outils au cerveau,
sous forme d'une compétence. Les Réglages lisent `statuses()`, cochent ou décochent, et
connectent un compte (`sign_in`) quand un serveur distant en demande un, ajoutent ou retirent
un serveur et choisissent ses outils, sans toucher au fichier à la main."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from friday.connectors import config
from friday.connectors.auth import Account
from friday.connectors.link import Link
from friday.connectors.tools import McpTool, pick, skill_for

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Offer:
    """Un outil d'un serveur branché, pour le choix des outils dans les Réglages."""

    name: str  # le nom chez le serveur
    title: str
    size: int  # caractères de schéma donnés au modèle
    read_only: bool
    given: bool  # donné au modèle aujourd'hui


@dataclass(frozen=True)
class Status:
    name: str
    where: str  # la commande ou l'url
    enabled: bool
    state: str  # « branché », « connexion… », « coupé », « à connecter », « en panne »
    detail: str  # l'erreur, ou les outils
    tools: tuple[str, ...] = ()
    signed_in: bool = False  # un compte est connecté (serveur distant)


class Connectors:
    def __init__(self, path: Path, toolbox, toolset, logs_dir: Path | None = None,
                 make_link: Callable[..., Link] = Link,
                 accounts_dir: Path | None = None) -> None:  # fmt: skip
        self.path, self.toolbox, self.toolset = path, toolbox, toolset
        self.logs_dir, self.make_link = logs_dir, make_link
        self.accounts_dir = accounts_dir  # data/mcp_comptes : les jetons des serveurs distants
        self.links: dict[str, Link] = {}
        self.given: dict[str, list[McpTool]] = {}  # les outils donnés au cerveau, par serveur
        self.pending: set[str] = set()
        self.listeners: list[Callable[[], None]] = []  # les Réglages, prévenus d'un changement
        self._lock = threading.Lock()

    def start(self) -> None:
        """Branche tous les serveurs cochés, chacun dans son fil."""
        for server in config.load(self.path):
            if server.enabled:
                self._connect_later(server)

    def account(self, server: config.Server) -> Account | None:
        if not server.url or self.accounts_dir is None:
            return None
        return Account(self.accounts_dir / f"{server.slug}.json")

    def _connect_later(self, server: config.Server, login: bool = False) -> None:
        with self._lock:
            if server.name in self.pending:
                return
            self.pending.add(server.name)
        threading.Thread(target=self._connect, args=(server, login), daemon=True,
                         name=f"mcp-start-{server.slug}").start()  # fmt: skip
        self._changed()

    def _connect(self, server: config.Server, login: bool = False) -> None:
        self._drop(server.name)
        link = self.make_link(server, self.logs_dir, account=self.account(server))
        with self._lock:
            self.links[server.name] = link
        if link.connect(login):
            self._give(server, link)
            log.info("Connecteur « %s » branché : %d outil(s) sur %d", server.name,
                     len(self.given.get(server.name, [])), len(link.tools))  # fmt: skip
        with self._lock:
            self.pending.discard(server.name)
        self._changed()

    def _give(self, server: config.Server, link: Link) -> None:
        """Donne au cerveau les outils choisis du serveur, en une compétence."""
        tools = pick([McpTool(link, t) for t in link.tools], server.tools)
        with self._lock:
            self.given[server.name] = tools
        for tool in tools:
            self.toolbox.add(tool, always=False)
        if tools:
            self.toolset.add_skill(skill_for(link, tools))

    def _take_back(self, name: str, link: Link) -> None:
        with self._lock:
            given = self.given.pop(name, [])
        self.toolset.remove_skill(f"mcp_{link.server.slug}")
        for tool in given:
            self.toolbox.remove(tool.name)

    def _drop(self, name: str) -> None:
        with self._lock:
            link = self.links.pop(name, None)
        if link is None:
            return
        self._take_back(name, link)
        link.close()

    def set_enabled(self, name: str, on: bool) -> None:
        config.set_enabled(self.path, name, on)
        server = self._server(name)
        if on and server is not None:
            self._connect_later(server)
        else:
            self._drop(name)
            self._changed()

    def _server(self, name: str) -> config.Server | None:
        return next((s for s in config.load(self.path) if s.name == name), None)

    def sign_in(self, name: str) -> None:
        """Ouvre le navigateur pour connecter le compte du serveur (puis le branche)."""
        server = self._server(name)
        if server is not None and server.enabled:
            self._connect_later(server, login=True)

    def sign_out(self, name: str) -> None:
        """Oublie le jeton du serveur ; il redemandera un compte."""
        server = self._server(name)
        account = self.account(server) if server is not None else None
        if account is None:
            return
        self._drop(name)
        account.sign_out()
        if server.enabled:
            self._connect_later(server)
        self._changed()

    def add(self, name: str, entry: dict) -> str:
        """Ajoute un serveur au fichier et le branche ; renvoie ce qui ne va pas (vide : fait)."""
        problem = config.add(self.path, name, entry)
        server = None if problem else self._server(name.strip())
        if server is not None and server.enabled:
            self._connect_later(server)
        self._changed()
        return problem

    def remove(self, name: str) -> None:
        """Retire le serveur du fichier, et oublie son compte."""
        server = self._server(name)
        self._drop(name)
        account = self.account(server) if server is not None else None
        if config.remove(self.path, name) and account is not None:
            account.sign_out()
        self._changed()

    def offers(self, name: str) -> list[Offer]:
        """Tous les outils du serveur branché (vide s'il ne l'est pas)."""
        link = self.links.get(name)
        if link is None or not link.connected:
            return []
        given = {t.remote for t in self.given.get(name, [])}
        tools = [McpTool(link, t) for t in link.tools]
        return [Offer(t.remote, t.title, t.size, not t.needs_confirmation, t.remote in given)
                for t in tools]  # fmt: skip

    def set_tools(self, name: str, tools: list[str]) -> None:
        """Les outils donnés au modèle, changés tout de suite (sans rebrancher)."""
        server = self._server(name) if config.set_tools(self.path, name, tools) else None
        link = self.links.get(name)
        if server is not None and link is not None and link.connected:
            self._take_back(name, link)
            self._give(server, link)
        self._changed()

    def reload(self) -> None:
        """Fichier modifié : tout est rebranché (serveurs ajoutés, changés ou retirés)."""
        for name in list(self.links):
            self._drop(name)
        self.start()
        self._changed()

    def statuses(self) -> list[Status]:
        result = []
        for server in config.load(self.path):
            link = self.links.get(server.name)
            if server.name in self.pending:
                state, detail, tools = "connexion…", "", ()
            elif not server.enabled:
                state, detail, tools = "coupé", "", ()
            elif link is not None and link.connected:
                tools = tuple(t.remote for t in self.given.get(server.name, []))
                state, detail = "branché", f"{len(tools)} outil(s)"
                if len(tools) < len(link.tools):
                    detail = (f"{len(tools)} outils donnés à Friday sur {len(link.tools)} "
                              "(la liste « outils » du fichier choisit lesquels)")  # fmt: skip
            elif link is not None and link.needs_login:
                state, detail, tools = "à connecter", "il demande un compte", ()
            else:
                state, detail, tools = "en panne", (link.error if link else ""), ()
            account = self.account(server)
            result.append(Status(server.name, server.where, server.enabled, state, detail, tools,
                                 bool(account and account.signed_in)))  # fmt: skip
        return result

    def _changed(self) -> None:
        for listener in list(self.listeners):
            try:
                listener()
            except Exception:  # une page de réglages fermée ne doit rien casser
                log.exception("Connecteurs : prévenir les réglages a échoué")

    def close(self) -> None:
        for name in list(self.links):
            self._drop(name)
