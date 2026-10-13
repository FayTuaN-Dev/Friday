"""Le globe de la veille monde (J9b) : les thèmes du moment, placés sur leur région (marqués
quand ils touchent les marchés de l'utilisateur), et les catastrophes en cours. La page du
globe choisit les couleurs (celle de l'interface pour « mine »)."""

from friday.trading.instruments import Instrument
from friday.world.digest import World, _title, describe, names
from friday.world.sources import KINDS, WorldUnavailable
from friday.world.themes import CENTERS

MAX_DISASTERS = 12


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'s' if count > 1 else ''}"


def article_links(world: World) -> dict[str, str]:
    """Titre affiché → lien de l'article (clic sur l'étiquette du globe)."""
    try:
        return {_title(h): h.link for h in world.headlines() if h.link}
    except WorldUnavailable:
        return {}


def globe(world: World, instruments: list[Instrument]) -> tuple[str, dict]:
    """(phrase à dire, données de la scène « world ») ; les points ont un `kind` : « mine »
    (thème qui touche ses marchés), « theme », « red » ou « orange » (catastrophes)."""
    points, mine = [], 0
    links = article_links(world)
    for theme, items in world.themes(None):
        lat, lon = CENTERS[theme.name]
        own = any(theme.concerns(i) for i in instruments)
        mine += own
        points.append({"lat": lat, "lon": lon, "label": theme.name, "detail": items[0],
                       "url": links.get(items[0], ""), "kind": "mine" if own else "theme",
                       "size": min(16, 7 + 2 * len(items))})  # fmt: skip
    themes = len(points)
    try:
        disasters = world.disasters()[:MAX_DISASTERS]
    except WorldUnavailable:
        disasters = []
    for d in disasters:
        size = f" {d.magnitude:g}".replace(".", ",") if d.magnitude else ""
        points.append({"lat": d.lat, "lon": d.lon, "label": f"{KINDS[d.kind].capitalize()}{size}",
                       "detail": describe(d), "kind": "red" if d.level == "Red" else "orange",
                       "size": 9 if d.level == "Red" else 7})  # fmt: skip
    if not points:
        return "Dis EXACTEMENT : « Rien de marquant dans le monde en ce moment. »", {"points": []}
    spoken = f"Voici le monde en ce moment : {plural(themes, 'sujet')} dans l'actualité"
    if instruments and mine:
        spoken += f", dont {mine} pour {names(instruments)}"
    if disasters:
        spoken += f", plus {plural(len(disasters), 'catastrophe')} en cours"
    return f"Dis EXACTEMENT : « {spoken}. »", {"points": points}
