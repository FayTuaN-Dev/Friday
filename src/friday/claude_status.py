"""Relais des limites Claude vers Friday. Claude Code donne à sa ligne d'état (« statusLine »)
le pourcentage utilisé de la session (5 h) et de la semaine, avec l'heure de remise à zéro
(champ « rate_limits », abonnés seulement). Ce script, branché comme ligne d'état :
- garde ces chiffres dans data/claude_limits.json, que Friday affiche ;
- écrit une ligne courte sous la zone de saisie de Claude Code.

Il ne lit que ce que Claude Code lui donne ; rien ne part en ligne. Il ne doit JAMAIS faire
échouer la ligne d'état : toute erreur est avalée.

Brancher (une fois) : Réglages → Diagnostic → « Brancher Claude Code », ou
`python -m friday.claude_status --installer`.
"""

import json
import shutil
import sys
import time
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
LIMITS = DATA / "claude_limits.json"
CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"


def relay(raw: str, target: Path = LIMITS, now: float | None = None) -> str:
    """JSON de Claude Code → fichier des limites ; renvoie la ligne d'état à afficher."""
    try:
        limits = json.loads(raw or "{}").get("rate_limits") or {}
    except (ValueError, AttributeError):
        limits = {}
    found = {}
    for key in ("five_hour", "seven_day"):
        window = limits.get(key) or {}
        used = window.get("used_percentage")
        if isinstance(used, int | float):
            reset = window.get("resets_at") or window.get("reset_at")  # (les deux noms vus)
            found[key] = {"used": float(used), "resets_at": reset}
    if not found:
        return "Friday : limites Claude indisponibles"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({**found, "updated": now or time.time()}), "utf-8")
    except OSError:
        pass
    labels = (("five_hour", "session"), ("seven_day", "semaine"))
    parts = [f"{label} {100 - found[key]['used']:.0f} % restants"
             for key, label in labels if key in found]  # fmt: skip
    return "Claude : " + " · ".join(parts)


def command() -> str:
    """La commande que Claude Code lance : le Python de Friday et ce module."""
    return f'"{Path(sys.executable).as_posix()}" -m friday.claude_status'


def install(settings: Path = CLAUDE_SETTINGS) -> str:
    """Branche le relais dans Claude Code (copie de sécurité d'abord) ; renvoie un message."""
    data = json.loads(settings.read_text("utf-8")) if settings.is_file() else {}
    current = (data.get("statusLine") or {}).get("command", "")
    if "friday.claude_status" in current:
        return "Déjà branché."
    if current:
        return ("Claude Code a déjà une ligne d'état personnalisée : je n'y touche pas. Remplacez "
                f"sa commande par : {command()}")  # fmt: skip
    if settings.is_file():
        shutil.copy2(settings, settings.with_name(settings.name + ".avant-friday"))
    data["statusLine"] = {"type": "command", "command": command()}
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    return "Branché : les limites s'afficheront après la prochaine réponse de Claude Code."


def main() -> None:
    if "--installer" in sys.argv:
        print(install())
        return
    try:
        print(relay(sys.stdin.read()))
    except Exception:  # la ligne d'état ne doit jamais casser Claude Code
        print("Friday")


if __name__ == "__main__":
    main()
