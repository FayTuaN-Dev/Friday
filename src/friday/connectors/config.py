"""Le fichier des connecteurs, data/mcp.json, écrit à la main ou depuis les Réglages :

    {"serveurs": {
        "notes": {"commande": "npx", "arguments": ["-y", "un-serveur-mcp"], "env": {},
                  "description": "mes notes", "mots_cles": ["note"], "actif": true,
                  "outils": ["search", "fetch"]},
        "distant": {"url": "https://exemple.com/mcp", "actif": false}}}

Un serveur local se lance avec `commande` (et `arguments`, `env`) ; un serveur distant se
joint par `url`. `description` (une ligne) dit au modèle à quoi il sert ; `mots_cles` (débuts
de mots, sans accents) l'aident à le choisir ; `outils` (facultatif) choisit les outils
donnés au modèle, sinon ce sont les premiers. Une entrée illisible est ignorée, pas fatale."""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)
TEMPLATE = {"serveurs": {}}


@dataclass(frozen=True)
class Server:
    name: str
    command: str = ""
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict, hash=False)
    url: str = ""
    enabled: bool = True
    description: str = ""
    keywords: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()  # « outils » : ceux à donner au modèle (vide : les premiers)

    @property
    def slug(self) -> str:
        """Le nom réduit à ce qu'accepte un nom d'outil (lettres, chiffres, _)."""
        return re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")[:20] or "serveur"

    @property
    def where(self) -> str:
        return self.url or " ".join((self.command, *self.args))


def _server(name: str, entry: dict) -> Server | None:
    if not isinstance(entry, dict):
        return None
    command, url = str(entry.get("commande") or ""), str(entry.get("url") or "")
    if bool(command) == bool(url):  # l'un ou l'autre
        log.warning("Connecteur « %s » ignoré : il faut une commande OU une url", name)
        return None
    args = entry.get("arguments") or []
    env = entry.get("env") or {}
    keywords = entry.get("mots_cles") or []
    tools = entry.get("outils") or []
    return Server(name, command, tuple(str(a) for a in args),
                  {str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else {},
                  url, entry.get("actif", True) is not False,
                  str(entry.get("description") or ""),
                  tuple(str(k).lower() for k in keywords),
                  tuple(str(t) for t in tools) if isinstance(tools, list) else ())  # fmt: skip


def _empty() -> dict:
    return {"serveurs": {}}  # neuf à chaque fois : il sera modifié


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return _empty()
    except (OSError, ValueError) as error:
        log.warning("%s illisible : %s", path.name, error)
        return _empty()
    return data if isinstance(data, dict) else _empty()


def problem(path: Path) -> str:
    """Pourquoi le fichier n'est pas compris (vide s'il va bien, ou s'il n'existe pas)."""
    try:
        data = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return ""
    except json.JSONDecodeError as error:
        return (f"erreur ligne {error.lineno}, colonne {error.colno} : il manque sans doute "
                "une virgule, une accolade ou un guillemet")  # fmt: skip
    except (OSError, ValueError) as error:
        return str(error)
    if not isinstance(data, dict) or not isinstance(data.get("serveurs"), dict):
        return 'il faut la forme {"serveurs": {...}}'
    return ""


def load(path: Path) -> list[Server]:
    entries = _read(path).get("serveurs")
    if not isinstance(entries, dict):
        return []
    servers = [_server(str(name), entry) for name, entry in entries.items()]
    return [s for s in servers if s is not None]


def _change(path: Path, change) -> bool:
    """Modifie l'entrée d'un serveur (le reste du fichier est gardé tel quel). Un fichier mal
    écrit n'est jamais réécrit : ce qu'il contient serait perdu."""
    if problem(path):
        return False
    data = _read(path)
    servers = data.setdefault("serveurs", {})
    if change(servers) is False:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    return True


def _update(name: str, **fields):
    def change(servers: dict):
        entry = servers.get(name)
        if not isinstance(entry, dict):
            return False
        entry.update(fields)

    return change


def set_enabled(path: Path, name: str, on: bool) -> None:
    """Coche ou décoche un serveur dans le fichier."""
    _change(path, _update(name, actif=on))


def set_tools(path: Path, name: str, tools: list[str]) -> bool:
    """Les outils donnés au modèle (liste « outils ») ; vide : les premiers, comme sans liste."""
    return _change(path, _update(name, outils=list(tools)))


def add(path: Path, name: str, entry: dict) -> str:
    """Ajoute un serveur ; renvoie ce qui ne va pas (vide si c'est fait)."""
    name = name.strip()
    if not name:
        return "donnez-lui un nom"
    if _server(name, entry) is None:
        return "il faut une adresse (en ligne) ou une commande (sur ce PC)"
    if problem(path):
        return "le fichier mcp.json est mal écrit : corrigez-le d'abord"

    def change(servers: dict):
        if name in servers:
            return False
        servers[name] = entry

    return "" if _change(path, change) else f"un connecteur s'appelle déjà « {name} »"


def remove(path: Path, name: str) -> bool:
    def change(servers: dict):
        if servers.pop(name, None) is None:
            return False

    return _change(path, change)


def ensure(path: Path) -> None:
    """Crée le fichier vide s'il n'existe pas (pour l'ouvrir depuis les Réglages)."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(TEMPLATE, indent=2), "utf-8")
