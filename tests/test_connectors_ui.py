"""Ajouter, choisir les outils et supprimer un connecteur depuis les Réglages (MC3), sans
écrire data/mcp.json à la main. Le serveur de test tourne dans le processus, sans réseau."""

import json

from test_connectors import FakeToolset, in_process_link, wait, write

from friday.connectors import config
from friday.connectors.manager import Connectors
from friday.tools.base import ToolBox


def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_config_is_edited_without_losing_the_rest(tmp_path):
    path = tmp_path / "mcp.json"
    assert config.add(path, " notes ", {"url": "https://x/mcp", "mots_cles": ["note"]}) == ""
    assert "déjà" in config.add(path, "notes", {"url": "https://y/mcp"})
    assert config.add(path, "", {"url": "u"}) and config.add(path, "vide", {})
    assert config.set_tools(path, "notes", ["lire"]) and config.load(path)[0].tools == ("lire",)
    assert config.remove(path, "notes") and not config.remove(path, "notes")
    path.write_text('{"serveurs": {"a": {"url": "u"}} "oups"}', "utf-8")  # mal écrit
    assert "mal écrit" in config.add(path, "b", {"url": "v"})
    assert not config.remove(path, "a")
    assert path.read_text("utf-8").endswith('"oups"}')  # jamais réécrit : rien de perdu


def test_typed_arguments_and_keys():
    from friday.ui.desktop.settings.connector_form import parse_keys, split_args

    assert split_args('-y "C:\\Mes docs\\notes" --vite') == ["-y", "C:\\Mes docs\\notes", "--vite"]
    assert split_args('"pas fermé') == ['"pas', "fermé"]
    assert parse_keys("API_KEY = abc=1\npas une clé\n=x") == {"API_KEY": "abc=1"}


def test_form_adds_a_ready_made_or_own_connector(tmp_path):
    from friday.ui.desktop.settings.connectors_page import ConnectorsPage

    app()
    path = tmp_path / "mcp.json"
    connectors = Connectors(path, ToolBox([]), FakeToolset(), make_link=in_process_link)
    page = ConnectorsPage(connectors)
    form = page.form
    try:
        form.preset.setCurrentIndex(form.preset.findText("Notion"))
        assert form.url.text() == "https://mcp.notion.com/mcp" and form.url.isVisibleTo(form)
        assert not form.command.isVisibleTo(form) and "notion-search" in form.entry()["outils"]
        form.preset.setCurrentIndex(form.preset.findText("Heure"))
        assert form.command.text() == "uvx" and form.command.isVisibleTo(form)
        assert form.submit()
        wait(connectors)
        entry = json.loads(path.read_text("utf-8"))["serveurs"]["heure"]
        assert entry["arguments"] == ["mcp-server-time", "--local-timezone=Europe/Paris"]
        assert connectors.statuses()[0].state == "branché"

        form.preset.setCurrentIndex(0)  # le sien : un programme, ses arguments, ses clés
        form.name.setText("heure")
        form.kind.setCurrentText("Sur ce PC (un programme)")
        form.command.setText("npx")
        form.args.setText("-y mon-serveur")
        form.keys.setPlainText("TOKEN=secret")
        assert not form.submit() and "déjà" in form.status.text()
        form.name.setText("perso")
        assert form.submit()
        wait(connectors)
        entry = json.loads(path.read_text("utf-8"))["serveurs"]["perso"]
        assert entry["commande"] == "npx" and entry["arguments"] == ["-y", "mon-serveur"]
        assert entry["env"] == {"TOKEN": "secret"} and "outils" not in entry
    finally:
        connectors.close()


def test_tools_are_picked_and_a_connector_removed(tmp_path):
    from friday.ui.desktop.settings.connectors_page import ConnectorsPage

    app()
    path = write(tmp_path / "mcp.json", {"faux": {"commande": "x"}})
    box = ToolBox([])
    connectors = Connectors(path, box, FakeToolset(), make_link=in_process_link)
    connectors.start()
    wait(connectors)
    page = ConnectorsPage(connectors)
    try:
        page.rows.itemAt(0).widget().tools.click()  # « Outils »
        picker = page.picker
        assert {o.name for o in picker.offers} == {"add", "save_note", "fail"}
        for offer, box_ in zip(picker.offers, picker.boxes, strict=True):
            box_.setChecked(offer.name == "add")
        assert picker.save_button.isEnabled() and "1 outil(s)" in picker.weight.text()
        picker.save_button.click()
        assert config.load(path)[0].tools == ("add",) and page.picking is None
        assert box.find("mcp_faux_add") and box.find("mcp_faux_save_note") is None
        assert connectors.statuses()[0].tools == ("add",)  # sans rebrancher

        page.rows.itemAt(0).widget().remove.click()
        assert config.load(path)  # un clic : on demande de confirmer
        page.rows.itemAt(0).widget().remove.click()
        assert config.load(path) == [] and box.find("mcp_faux_add") is None
    finally:
        connectors.close()
