"""Les connecteurs de Friday : relit data/mcp.json, branche chaque serveur coché en arrière-plan
(un serveur lent ou en panne ne retarde ni ne bloque rien) et donne ses outils au cerveau,
sous forme d'une compétence. Les Réglages lisent `statuses()` et cochent ou décochent."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from friday.connectors import config
from friday.connectors.link import Link
from friday.connectors.tools import McpTool, skill_for

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Status:
    name: str
    where: str  # la commande ou l'url
    enabled: bool
    state: str  # « branché », « connexion… », « coupé », « en panne »
    detail: str  # l'erreur, ou les outils
    tools: tuple[str, ...] = ()


class Connectors:
    def __init__(self, path: Path, toolbox, toolset, logs_dir: Path | None = None,
                 make_link: Callable[..., Link] = Link) -> None:  # fmt: skip
        self.path, self.toolbox, self.toolset = path, toolbox, toolset
        self.logs_dir, self.make_link = logs_dir, make_link
        self.links: dict[str, Link] = {}
        self.pending: set[str] = set()
        self.listeners: list[Callable[[], None]] = []  # les Réglages, prévenus d'un changement
        self._lock = threading.Lock()

    def start(self) -> None:
        """Branche tous les serveurs cochés, chacun dans son fil."""
        for server in config.load(self.path):
            if server.enabled:
                self._connect_later(server)

    def _connect_later(self, server: config.Server) -> None:
        with self._lock:
            if server.name in self.pending:
                return
            self.pending.add(server.name)
        threading.Thread(target=self._connect, args=(server,), daemon=True,
                         name=f"mcp-start-{server.slug}").start()  # fmt: skip
        self._changed()

    def _connect(self, server: config.Server) -> None:
        self._drop(server.name)
        link = self.make_link(server, self.logs_dir)
        with self._lock:
            self.links[server.name] = link
        if link.connect():
            tools = [McpTool(link, t) for t in link.tools]
            for tool in tools:
                self.toolbox.add(tool, always=False)
            if tools:
                self.toolset.add_skill(skill_for(link, tools))
            log.info("Connecteur « %s » branché : %d outil(s)", server.name, len(tools))
        with self._lock:
            self.pending.discard(server.name)
        self._changed()

    def _drop(self, name: str) -> None:
        with self._lock:
            link = self.links.pop(name, None)
        if link is None:
            return
        self.toolset.remove_skill(f"mcp_{link.server.slug}")
        for tool in link.tools:
            self.toolbox.remove(McpTool(link, tool).name)
        link.close()

    def set_enabled(self, name: str, on: bool) -> None:
        config.set_enabled(self.path, name, on)
        server = next((s for s in config.load(self.path) if s.name == name), None)
        if on and server is not None:
            self._connect_later(server)
        else:
            self._drop(name)
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
                tools = tuple(t.name for t in link.tools)
                state, detail = "branché", f"{len(tools)} outil(s)"
            else:
                state, detail, tools = "en panne", (link.error if link else ""), ()
            result.append(Status(server.name, server.where, server.enabled, state, detail, tools))
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
