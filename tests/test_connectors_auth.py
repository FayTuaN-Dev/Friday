"""La connexion par compte des connecteurs MCP (MC2) : jeton gardé, page de retour, et un vrai
serveur à compte sur 127.0.0.1 (tests/fixtures), sans navigateur ni réseau."""

import asyncio
import json
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest
from mcp.shared.auth import OAuthToken

from friday.connectors import auth
from friday.connectors.auth import Account, LoginNeeded
from friday.connectors.link import Link
from friday.connectors.manager import Connectors
from friday.tools.base import ToolBox

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from mcp_oauth_server import Running  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def browser(url: str) -> None:
    """Le « navigateur » : suit la page de connexion jusqu'à la page de retour de Friday."""
    threading.Thread(target=lambda: urllib.request.urlopen(url, timeout=10).read(),
                     daemon=True).start()  # fmt: skip


def test_account_keeps_the_token_and_forgets_it(tmp_path):
    account = Account(tmp_path / "comptes" / "x.json")
    assert not account.signed_in and asyncio.run(account.get_tokens()) is None
    token = OAuthToken(access_token="a", expires_in=60, refresh_token="r")
    asyncio.run(account.set_tokens(token))
    assert account.signed_in and asyncio.run(account.get_tokens()).refresh_token == "r"
    assert time.time() < account.expires_at <= time.time() + 60
    account.sign_out()
    assert not account.path.exists() and not account.signed_in


def test_callback_page_hands_over_the_code():
    port = free_port()

    async def scenario(query: str):
        server, code = await auth._listen(port)
        url = f"http://127.0.0.1:{port}/callback?{query}"
        page = asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=5).read().decode())
        text, result = await asyncio.gather(page, auth._wait_for_code(server, code),
                                            return_exceptions=True)  # fmt: skip
        return text, result

    text, result = asyncio.run(scenario("code=abc&state=s1"))
    assert "Friday est connecté" in text and (result.code, result.state) == ("abc", "s1")
    text, result = asyncio.run(scenario("error=access_denied"))
    assert "pas abouti" in text and isinstance(result, LoginNeeded)


@pytest.fixture
def remote():
    running = Running(free_port())
    yield running
    running.stop()


def wait(connectors, seconds=20.0):
    end = time.monotonic() + seconds
    while connectors.pending and time.monotonic() < end:
        time.sleep(0.05)
    assert not connectors.pending


class FakeToolset:
    def __init__(self):
        self.skills = {}

    def add_skill(self, skill):
        self.skills[skill.name] = skill

    def remove_skill(self, name):
        self.skills.pop(name, None)


def test_remote_server_asks_for_an_account_then_keeps_it(tmp_path, remote):
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"serveurs": {"compte": {"url": remote.url}}}), "utf-8")
    port, opened = free_port(), []

    def make_link(server, logs, account=None):
        def open_url(url):
            opened.append(url)
            browser(url)

        return Link(server, logs, account=Account(account.path, port), open_url=open_url)

    box = ToolBox([])
    connectors = Connectors(path, box, FakeToolset(), tmp_path, make_link, tmp_path / "comptes")
    connectors.start()
    wait(connectors)
    try:
        (status,) = connectors.statuses()
        assert status.state == "à connecter" and not status.signed_in and not opened
        connectors.sign_in("compte")  # le bouton « Se connecter »
        wait(connectors)
        (status,) = connectors.statuses()
        assert status.state == "branché" and status.signed_in and len(opened) == 1
        assert box.find("mcp_compte_hello").run(name="Val").text == "bonjour Val"

        saved = json.loads((tmp_path / "comptes" / "compte.json").read_text("utf-8"))
        saved["expire"] = time.time() - 10  # jeton périmé : rafraîchi, sans navigateur
        (tmp_path / "comptes" / "compte.json").write_text(json.dumps(saved), "utf-8")
        connectors.reload()
        wait(connectors)
        assert connectors.statuses()[0].state == "branché"
        assert len(opened) == 1 and remote.provider.logins == 1

        connectors.sign_out("compte")  # « Se déconnecter »
        wait(connectors)
        (status,) = connectors.statuses()  # le jeton est oublié (l'inscription peut rester)
        assert status.state == "à connecter" and not status.signed_in
    finally:
        connectors.close()


def test_settings_page_shows_the_account_buttons(tmp_path, remote):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.connectors_page import ConnectorsPage

    QApplication.instance() or QApplication([])
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"serveurs": {"compte": {"url": remote.url}}}), "utf-8")
    connectors = Connectors(path, ToolBox([]), FakeToolset(), tmp_path,
                            accounts_dir=tmp_path / "comptes")  # fmt: skip
    connectors.start()
    wait(connectors)
    try:
        page = ConnectorsPage(connectors)
        assert page.rows.itemAt(0).widget().account.text() == "Se connecter"
    finally:
        connectors.close()
