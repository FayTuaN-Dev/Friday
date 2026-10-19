"""Les connecteurs MCP (MC1) : fichier, liaison, outils, compétence, page des réglages.
Rien de réel : un petit serveur MCP de test (tests/fixtures), sans réseau."""

import importlib.util
import json
import sys
import time
from pathlib import Path

from friday.brain.router import SkillRouter
from friday.brain.skills import SKILLS
from friday.brain.toolset import Toolset
from friday.connectors import config
from friday.connectors import tools as mcp_tools
from friday.connectors.link import Link
from friday.connectors.manager import Connectors
from friday.connectors.tools import McpTool, compact, pick, skill_for
from friday.tools.base import ToolBox

FAKE = Path(__file__).parent / "fixtures" / "mcp_fake_server.py"


def fake_server():
    """Un serveur neuf à chaque fois (ses notes repartent de zéro)."""
    spec = importlib.util.spec_from_file_location("mcp_fake_server", FAKE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.server


def in_process(server, errlog, http=None):
    return fake_server()  # le client mcp sait joindre un serveur dans le même processus


def in_process_link(server, logs, account=None):
    return Link(server, logs, make_target=in_process)


def write(path: Path, servers: dict) -> Path:
    path.write_text(json.dumps({"serveurs": servers}), "utf-8")
    return path


def test_config_reads_servers_and_skips_bad_entries(tmp_path):
    path = write(tmp_path / "mcp.json", {
        "Mes Notes!": {"commande": "npx", "arguments": ["-y", "x"], "mots_cles": ["Note"],
                       "description": "mes notes", "env": {"K": 1}, "outils": ["lire"]},
        "distant": {"url": "https://exemple.com/mcp", "actif": False},
        "les deux": {"commande": "a", "url": "b"}, "rien": {}, "pas un objet": 3,
    })  # fmt: skip
    notes, remote = config.load(path)
    assert notes.slug == "mes_notes" and notes.args == ("-y", "x") and notes.env == {"K": "1"}
    assert notes.keywords == ("note",) and notes.enabled and notes.where == "npx -y x"
    assert notes.tools == ("lire",) and remote.tools == ()
    assert remote.url and not remote.enabled
    config.set_enabled(path, "distant", True)
    assert config.load(path)[1].enabled
    assert config.load(tmp_path / "absent.json") == []
    (tmp_path / "casse.json").write_text('{"serveurs": {"a": {}}\n "b": {}}', "utf-8")
    assert config.load(tmp_path / "casse.json") == []
    assert "ligne 2" in config.problem(tmp_path / "casse.json")
    assert config.problem(path) == "" and config.problem(tmp_path / "absent.json") == ""


def test_tools_wrap_the_server_and_ask_before_changing_data():
    link = Link(config.Server("faux", command="x"), make_target=in_process)
    assert link.connect(), link.error
    try:
        tools = {t.name: McpTool(link, t) for t in link.tools}
        add, save, fail = tools["add"], tools["save_note"], tools["fail"]
        assert add.name == "mcp_faux_add" and set(add.required) == {"a", "b"}
        assert not add.needs_confirmation and save.needs_confirmation  # lecture seule déclarée
        assert "modifier des données" in save.confirmation({"text": "lait"})
        result = add.run(a=2, b=3, reason="facultatif")
        assert result.ok and result.text == "5"
        assert save.run(text="lait").text == "saved 1"
        assert not fail.run().ok
        assert fail.schema()["function"]["parameters"]["properties"]  # paramètre de façade
        assert add.run(a=1, b=1, cursor=None, page="").text == "2"  # null de qwen : retirés
    finally:
        link.close()
    assert not link.connected
    assert link.call("add", {"a": 1, "b": 1}, 1)[1] is False  # débranché : échec, sans planter


def test_schemas_are_slimmed_and_only_a_few_tools_are_given(monkeypatch):
    sub = {"type": "string", "description": "longue"}
    slim = compact({"type": "object", "description": "x" * 300, "pattern": "^a$",
                    "properties": {"sub": sub}})  # fmt: skip
    assert len(slim["description"]) == mcp_tools.MAX_PARAM_TEXT and "pattern" not in slim
    assert slim["properties"]["sub"] == {"type": "string"}  # sous-champs sans description
    link = Link(config.Server("faux", command="x"), make_target=in_process)
    assert link.connect()
    try:
        tools = [McpTool(link, t) for t in link.tools]
        assert pick(tools)[0].remote == "add"  # lecture seule d'abord
        assert [t.remote for t in pick(tools, ("save_note", "add", "absent"))] == [
            "save_note", "add"]  # fmt: skip
        monkeypatch.setattr(mcp_tools, "MAX_TOTAL", tools[0].size)
        assert len(pick(tools)) == 1  # la mémoire de qwen est comptée
    finally:
        link.close()


def test_skill_is_routed_by_keywords_and_only_then_gives_its_tools():
    link = Link(config.Server("faux", command="x", description="des calculs",
                              keywords=("calcul",)), make_target=in_process)  # fmt: skip
    assert link.connect()
    try:
        box = ToolBox([])
        tools = [McpTool(link, t) for t in link.tools]
        for tool in tools:
            box.add(tool, always=False)
        toolset = Toolset(box, SkillRouter(SKILLS))
        toolset.add_skill(skill_for(link, tools))
        toolset.start("quelle heure est-il ?")
        assert "mcp_faux_add" not in toolset.tool_names()
        assert "mcp_faux" in toolset.schemas()[-1]["function"]["description"]  # load_skill
        toolset.start("fais un calcul pour moi")
        assert "mcp_faux_add" in toolset.tool_names() and "des calculs" in toolset.guides()
        assert toolset.load("mcp_faux").startswith("Compétence")
        toolset.remove_skill("mcp_faux")
        assert "mcp_faux_add" not in toolset.tool_names()
        assert toolset.load("mcp_faux").startswith("Compétence inconnue")
    finally:
        link.close()


class FakeToolset:
    def __init__(self):
        self.skills = {}

    def add_skill(self, skill):
        self.skills[skill.name] = skill

    def remove_skill(self, name):
        self.skills.pop(name, None)


def wait(connectors, seconds=10.0):
    end = time.monotonic() + seconds
    while connectors.pending and time.monotonic() < end:
        time.sleep(0.05)
    assert not connectors.pending


def test_connectors_plug_in_the_background_and_follow_the_switch(tmp_path):
    path = write(
        tmp_path / "mcp.json",
        {"faux": {"commande": "x"}, "coupé": {"commande": "y", "actif": False}},
    )
    box, toolset = ToolBox([]), FakeToolset()
    seen = []
    connectors = Connectors(path, box, toolset, make_link=in_process_link)
    connectors.listeners.append(lambda: seen.append(1))
    connectors.start()
    wait(connectors)
    try:
        assert box.find("mcp_faux_add") is not None and "mcp_faux_add" not in box.extra
        assert "mcp_faux" in toolset.skills and seen
        faux, off = connectors.statuses()
        assert faux.state == "branché" and "add" in faux.tools
        assert off.state == "coupé" and not off.enabled
        connectors.set_enabled("faux", False)
        assert box.find("mcp_faux_add") is None and not toolset.skills
        assert connectors.statuses()[0].state == "coupé"
        assert config.load(path)[0].enabled is False  # gardé dans le fichier
    finally:
        connectors.close()


def test_a_broken_server_is_reported_not_fatal(tmp_path):
    path = write(
        tmp_path / "mcp.json",
        {"cassé": {"commande": sys.executable, "arguments": ["-c", "raise SystemExit(3)"]}},
    )
    connectors = Connectors(path, ToolBox([]), FakeToolset(), logs_dir=tmp_path)
    connectors.start()
    wait(connectors, 40)
    (status,) = connectors.statuses()
    assert status.state == "en panne" and status.detail
    connectors.close()


def test_a_real_local_server_over_stdio(tmp_path):
    """De bout en bout : le serveur de test lancé comme un vrai programme."""
    server = config.Server("faux", command=sys.executable, args=(str(FAKE),))
    link = Link(server, tmp_path)
    assert link.connect(), link.error
    try:
        assert link.call("add", {"a": 20, "b": 22}, 10) == ("42", True)
    finally:
        link.close()
    assert (tmp_path / "mcp_faux.log").exists()


def test_settings_page_lists_servers_and_switches_them(tmp_path):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.connectors_page import ConnectorsPage

    QApplication.instance() or QApplication([])
    path = write(tmp_path / "mcp.json", {"faux": {"commande": "x", "actif": False}})
    connectors = Connectors(
        path,
        ToolBox([]),
        FakeToolset(),
        make_link=in_process_link,
    )
    page = ConnectorsPage(connectors)
    row = page.rows.itemAt(0).widget()
    assert not row.toggle.isChecked() and connectors.listeners
    row.toggle.click()
    wait(connectors)
    assert connectors.statuses()[0].state == "branché"
    connectors.close()
    assert not hasattr(ConnectorsPage(None), "rows")  # Friday pas encore chargée
    path.write_text('{"serveurs": {} "x"}', "utf-8")  # une virgule oubliée : c'est dit
    page.refresh()
    assert "pas compris" in page.rows.itemAt(0).widget().text()
