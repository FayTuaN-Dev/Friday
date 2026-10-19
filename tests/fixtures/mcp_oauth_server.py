"""Un serveur MCP distant de test qui demande un compte (OAuth), sur 127.0.0.1 : il accepte
toute demande de connexion, sans page à remplir. Rien ne sort de la machine."""

import secrets
import threading
import time

import uvicorn
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations


class Provider:
    def __init__(self) -> None:
        self.clients, self.codes, self.tokens, self.refresh = {}, {}, {}, {}
        self.logins = 0  # passages par la page de connexion

    async def get_client(self, client_id):
        return self.clients.get(client_id)

    async def register_client(self, client_info):
        self.clients[client_info.client_id] = client_info

    async def authorize(self, client, params):
        self.logins += 1
        code = secrets.token_hex(8)
        self.codes[code] = AuthorizationCode(
            code=code, scopes=params.scopes or [], expires_at=time.time() + 60,
            client_id=client.client_id, code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri, resource=params.resource,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly)  # fmt: skip
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client, code):
        return self.codes.get(code)

    def _issue(self, client_id, scopes, resource):
        from mcp.shared.auth import OAuthToken

        access, refresh = secrets.token_hex(8), secrets.token_hex(8)
        expires = int(time.time()) + 3600
        self.tokens[access] = AccessToken(token=access, client_id=client_id, scopes=scopes,
                                          expires_at=expires, resource=resource)  # fmt: skip
        self.refresh[refresh] = RefreshToken(token=refresh, client_id=client_id, scopes=scopes,
                                             resource=resource)  # fmt: skip
        return OAuthToken(access_token=access, expires_in=3600, refresh_token=refresh,
                          scope=" ".join(scopes) or None)  # fmt: skip

    async def exchange_authorization_code(self, client, code):
        self.codes.pop(code.code, None)
        return self._issue(client.client_id, code.scopes, code.resource)

    async def load_refresh_token(self, client, refresh_token):
        return self.refresh.get(refresh_token)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        self.refresh.pop(refresh_token.token, None)
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.resource)

    async def load_access_token(self, token):
        return self.tokens.get(token)

    async def revoke_token(self, token):
        self.tokens.pop(getattr(token, "token", ""), None)


class Running:
    """Le serveur lancé dans un fil ; `stop()` l'arrête."""

    def __init__(self, port: int) -> None:
        self.url = f"http://127.0.0.1:{port}/mcp"
        self.provider = Provider()
        server = MCPServer("compte", auth_server_provider=self.provider, auth=AuthSettings(
            issuer_url=f"http://127.0.0.1:{port}", resource_server_url=self.url,
            client_registration_options=ClientRegistrationOptions(enabled=True),
            validate_token_resource=True))  # fmt: skip

        @server.tool(annotations=ToolAnnotations(read_only_hint=True))
        def hello(name: str) -> str:
            """Dit bonjour."""
            return f"bonjour {name}"

        config = uvicorn.Config(server.streamable_http_app(), "127.0.0.1", port, log_level="error")
        self.uvicorn = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.uvicorn.run, daemon=True)
        self.thread.start()
        end = time.monotonic() + 10
        while not self.uvicorn.started and time.monotonic() < end:
            time.sleep(0.02)

    def stop(self) -> None:
        self.uvicorn.should_exit = True
        self.thread.join(5)
