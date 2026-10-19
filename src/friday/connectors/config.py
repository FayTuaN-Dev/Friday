"""Le fichier des connecteurs, data/mcp.json, écrit à la main ou depuis les Réglages :

    {"serveurs": {
        "notes": {"commande": "npx", "arguments": ["-y", "un-serveur-mcp"], "env": {},
                  "description": "mes notes", "mots_cles": ["note"], "actif": true},
        "distant": {"url": "https://exemple.com/mcp", "actif": false}}}

Un serveur local se lance avec `commande` (et `arguments`, `env`) ; un serveur distant se
joint par `url`. `description` (une ligne) dit au modèle à quoi il sert ; `mots_cles` (débuts
de mots, sans accents) l'aident à le choisir. Une entrée illisible est ignorée, pas fatale."""

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
    return Server(name, command, tuple(str(a) for a in args),
                  {str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else {},
                  url, entry.get("actif", True) is not False,
                  str(entry.get("description") or ""),
                  tuple(str(k).lower() for k in keywords))  # fmt: skip


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return dict(TEMPLATE)
    except (OSError, ValueError) as error:
        log.warning("%s illisible : %s", path.name, error)
        return dict(TEMPLATE)
    return data if isinstance(data, dict) else dict(TEMPLATE)


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


def set_enabled(path: Path, name: str, on: bool) -> None:
    """Coche ou décoche un serveur dans le fichier (le reste est gardé tel quel)."""
    data = _read(path)
    entry = data.get("serveurs", {}).get(name)
    if isinstance(entry, dict):
        entry["actif"] = on
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def ensure(path: Path) -> None:
    """Crée le fichier vide s'il n'existe pas (pour l'ouvrir depuis les Réglages)."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(TEMPLATE, indent=2), "utf-8")
