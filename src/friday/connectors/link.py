"""Une liaison avec un serveur MCP, tenue dans son propre fil (une boucle asyncio, comme
l'exige la bibliothèque mcp) : Friday l'appelle depuis ses fils ordinaires et attend la
réponse. Un serveur local est lancé sans fenêtre ; ce qu'il écrit en erreur va dans
logs/mcp_<nom>.log, pas dans la console."""

import asyncio
import logging
import threading
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from friday.connectors.config import Server

log = logging.getLogger(__name__)
CONNECT_TIMEOUT = 30.0  # un serveur lancé par npx peut d'abord s'installer
MAX_TEXT = 6000  # une réponse plus longue est coupée (la mémoire de qwen est comptée)


def describe(error: BaseException) -> str:
    """Le message utile d'une erreur, même enveloppée (groupes de tâches d'anyio)."""
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    if isinstance(error, TimeoutError):
        return "le serveur ne répond pas"
    return str(error) or type(error).__name__


def target(server: Server, errlog) -> Any:
    """Ce que le client mcp joint : l'url, ou le programme à lancer."""
    if server.url:
        return server.url
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(command=server.command, args=list(server.args),
                                   env=server.env or None)  # fmt: skip
    return stdio_client(params, errlog=errlog)


def result_text(result) -> str:
    parts = [getattr(block, "text", "") or f"[{getattr(block, 'type', 'contenu')}]"
             for block in result.content]  # fmt: skip
    text = "\n".join(p for p in parts if p).strip()
    if not text and result.structured_content is not None:
        text = str(result.structured_content)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "… (coupé)"


class Link:
    def __init__(self, server: Server, logs_dir: Path | None = None, make_target=target) -> None:
        self.server = server
        self.logs_dir = logs_dir
        self.make_target = make_target
        self.tools: list = []  # mcp_types.Tool
        self.error = ""
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._thread: threading.Thread | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(self) -> bool:
        """Lance la liaison et attend qu'elle soit prête (ou en échec)."""
        ready = threading.Event()
        self._thread = threading.Thread(target=lambda: asyncio.run(self._hold(ready)),
                                        daemon=True, name=f"mcp-{self.server.slug}")  # fmt: skip
        self._thread.start()
        ready.wait(CONNECT_TIMEOUT + 5)
        return self.connected

    async def _hold(self, ready: threading.Event) -> None:
        from mcp.client import Client

        self._loop, self._stop = asyncio.get_running_loop(), asyncio.Event()
        self.error = ""
        try:
            async with AsyncExitStack() as stack:
                errlog = None
                if self.logs_dir is not None and not self.server.url:
                    self.logs_dir.mkdir(parents=True, exist_ok=True)
                    path = self.logs_dir / f"mcp_{self.server.slug}.log"
                    errlog = stack.enter_context(path.open("a", encoding="utf-8"))
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    client = await stack.enter_async_context(
                        Client(self.make_target(self.server, errlog))
                    )
                    self.tools = await self._list(client)
                self._client = client
                ready.set()
                await self._stop.wait()
        except BaseException as error:  # noqa: BLE001 (un serveur en panne ne doit rien casser)
            self.error = describe(error)
            log.warning("Connecteur « %s » : %s", self.server.name, self.error)
        finally:
            self._client = None
            ready.set()

    @staticmethod
    async def _list(client) -> list:
        tools, cursor = [], None
        for _ in range(20):  # garde-fou : une pagination sans fin
            page = await client.list_tools(cursor=cursor)
            tools += page.tools
            cursor = page.next_cursor
            if not cursor:
                break
        return tools

    def call(self, name: str, arguments: dict, timeout: float) -> tuple[str, bool]:
        """(texte de la réponse, réussi ?) ; une liaison coupée ou un délai dépassé : échec."""
        client, loop = self._client, self._loop
        if client is None or loop is None:
            return f"Le connecteur « {self.server.name} » n'est pas branché.", False
        future = asyncio.run_coroutine_threadsafe(client.call_tool(name, arguments), loop)
        try:
            result = future.result(timeout)
        except Exception as error:
            future.cancel()
            return f"Échec de {name} : {describe(error)}", False
        return result_text(result) or "(réponse vide)", not result.is_error

    def close(self) -> None:
        loop, stop = self._loop, self._stop
        if loop is not None and stop is not None:
            try:
                loop.call_soon_threadsafe(stop.set)
            except RuntimeError:  # boucle déjà finie (le serveur s'est arrêté seul)
                pass
        if self._thread is not None:
            self._thread.join(5)
