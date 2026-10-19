"""La connexion par compte (OAuth) d'un serveur MCP distant. Le jeton reste sur ce PC, dans
data/mcp_comptes/<serveur>.json (jamais copié dans les sauvegardes). Au démarrage, Friday ne
fait que réutiliser un jeton déjà obtenu : le navigateur ne s'ouvre que quand on clique
« Se connecter » dans les Réglages, et la réponse revient sur une petite page locale."""

import asyncio
import json
import logging
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import (
    AuthorizationCodeResult,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)

log = logging.getLogger(__name__)
CALLBACK_PORT = 47615  # fixe : l'adresse de retour est enregistrée auprès du serveur
LOGIN_TIMEOUT = 300.0  # le temps de se connecter dans le navigateur
PAGE = ("<!doctype html><meta charset='utf-8'><title>Friday</title>"
        "<body style='font-family:sans-serif;background:#111;color:#eee;text-align:center;"
        "padding-top:20vh'><h2>{}</h2><p>Tu peux fermer cette page.</p>")  # fmt: skip


class LoginNeeded(Exception):
    """Le serveur demande un compte : à faire depuis les Réglages, pas au démarrage."""


def _not_login_needed(record: logging.LogRecord) -> bool:
    """mcp écrit toute la trace d'un échec de connexion : inutile pour un compte à connecter."""
    error = record.exc_info[1] if record.exc_info else None
    return not isinstance(error, LoginNeeded)


logging.getLogger("mcp.client.auth.oauth2").addFilter(_not_login_needed)


class Account:
    """Le jeton d'un serveur, gardé dans un fichier (format du TokenStorage de mcp)."""

    def __init__(self, path: Path, port: int = CALLBACK_PORT) -> None:
        self.path, self.port = path, port

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.port}/callback"

    @property
    def signed_in(self) -> bool:
        return bool(self._read().get("jeton"))

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, **changes) -> None:
        data = {**self._read(), **changes}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), "utf-8")

    @property
    def expires_at(self) -> float | None:
        return self._read().get("expire")

    async def get_tokens(self) -> OAuthToken | None:
        token = self._read().get("jeton")
        return OAuthToken.model_validate(token) if token else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        expire = time.time() + int(tokens.expires_in) if tokens.expires_in else None
        self._write(jeton=tokens.model_dump(mode="json"), expire=expire)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        client = self._read().get("client")
        return OAuthClientInformationFull.model_validate(client) if client else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._write(client=client_info.model_dump(mode="json", exclude_none=True))

    def sign_out(self) -> None:
        self.path.unlink(missing_ok=True)


class _Provider(OAuthClientProvider):
    async def _initialize(self) -> None:
        await super()._initialize()
        # mcp oublie l'échéance d'un jeton relu : sans elle, un jeton périmé ne serait pas
        # rafraîchi mais redemandé (navigateur) au premier refus du serveur
        self.context.token_expiry_time = self.context.storage.expires_at


async def _wait_for_code(server: asyncio.Server, code: asyncio.Future) -> AuthorizationCodeResult:
    try:
        return await code
    finally:
        server.close()


async def _listen(port: int) -> tuple[asyncio.Server, asyncio.Future]:
    """La page locale où le navigateur revient avec le code d'autorisation."""
    code: asyncio.Future = asyncio.get_running_loop().create_future()

    async def answer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = (await reader.readline()).decode("latin-1").split()
            url = urlparse(line[1] if len(line) > 1 else "/")
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            found = url.path == "/callback" and ("code" in query or "error" in query)
            if found and not code.done():
                if "code" in query:
                    code.set_result(
                        AuthorizationCodeResult(
                            code=query["code"], state=query.get("state"), iss=query.get("iss")
                        )
                    )
                else:
                    code.set_exception(LoginNeeded(f"connexion refusée ({query['error']})"))
            title = "Friday est connecté." if "code" in query else "La connexion n'a pas abouti."
            body = PAGE.format(title).encode()
            status = "200 OK" if found else "404 Not Found"
            writer.write(f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
                         f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                         + body)  # fmt: skip
            await writer.drain()
        finally:
            writer.close()

    return await asyncio.start_server(answer, "127.0.0.1", port), code


def provider(server_url: str, account: Account, login: bool,
             open_url: Callable[[str], object] = webbrowser.open):  # fmt: skip
    """L'authentification jointe aux requêtes ; sans `login`, un compte manquant est signalé
    (LoginNeeded) au lieu d'ouvrir le navigateur."""
    waiting: dict = {}

    async def redirect(url: str) -> None:
        if not login:
            raise LoginNeeded("connexion au compte à faire")
        waiting["server"], waiting["code"] = await _listen(account.port)
        open_url(url)

    async def callback() -> AuthorizationCodeResult:
        return await _wait_for_code(waiting["server"], waiting["code"])

    metadata = OAuthClientMetadata(client_name="Friday", redirect_uris=[account.redirect_uri],
                                   grant_types=["authorization_code", "refresh_token"],
                                   token_endpoint_auth_method="none")  # fmt: skip
    return _Provider(server_url, metadata, account, redirect, callback)
