"""L'espace sur le globe (M4) : « montre-moi l'ISS », « quand passe l'ISS au-dessus de chez
moi ? », « c'est quand le prochain lancement SpaceX ? ». Calculs : orbits.py ; données :
space_data.py."""

import math
from datetime import UTC, datetime, timedelta

import httpx

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.orbits import Pass, now, passes, track, where
from friday.tools.place import HEADERS, find_place
from friday.tools.space_data import SATELLITES, Busy, launches, orbit, overflown
from friday.voice.wake import normalize

DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
          "octobre", "novembre", "décembre")  # fmt: skip
BEHIND, AHEAD = 15, 95  # minutes de trace : un peu du passé, un tour complet à venir
PASS_HOURS = 72
PRECISE = ("Second", "Minute", "Hour")
BUSY = "Dis EXACTEMENT : « Le service de l'espace est saturé, redemandez-moi plus tard. »"


def day_text(when: datetime, today: datetime) -> str:
    """« aujourd'hui », « demain », « samedi » ou « samedi 24 octobre » (heure locale)."""
    gap = (when.date() - today.date()).days
    if gap == 0:
        return "aujourd'hui"
    if gap == 1:
        return "demain"
    day = DAYS[when.weekday()]
    return day if gap < 7 else f"{day} {when.day} {MONTHS[when.month - 1]}"


def hour_text(when: datetime) -> str:
    return f"{when.hour} h {when.minute:02d}"


def coming_from(side: str) -> str:
    return f"de l'{side}" if side[0] in "eo" else f"du {side}"


def going_to(side: str) -> str:
    return f"l'{side}" if side[0] in "eo" else f"le {side}"


def pass_text(p: Pass, today: datetime) -> str:
    local = p.start.astimezone()
    way = (f"vers {going_to(p.sets)}" if p.rises == p.sets
           else f"{coming_from(p.rises)} vers {going_to(p.sets)}")  # fmt: skip
    return (f"{day_text(local, today)} à {hour_text(local)}, pendant {p.minutes} min, jusqu'à "
            f"{p.highest}° au-dessus de l'horizon, {way}")  # fmt: skip


def launch_date(when: datetime, precision: str, today: datetime) -> str:
    """La date d'un lancement, aussi précise que ce qu'on sait (« en novembre » si seul le
    mois est prévu : pas de fausse heure). Sans heure, c'est la date du calendrier (UTC)."""
    if precision in PRECISE:
        return f"{day_text(when, today)} à {hour_text(when)}"
    when, unsure = when.astimezone(UTC), " (date à confirmer)"
    if precision == "Day" or precision.startswith("Week"):
        return f"vers le {when.day} {MONTHS[when.month - 1]} (heure à confirmer)"
    if precision == "Month":
        return f"en {MONTHS[when.month - 1]} {when.year}{unsure}"
    if precision.startswith("Quarter"):  # « Quarter 4 » : la date donnée est la fin du trimestre
        quarter = (when.month - 1) // 3 + 1
        return f"au {quarter}{'er' if quarter == 1 else 'e'} trimestre {when.year}{unsure}"
    if "Half" in precision:  # « Year Half 1 »
        return f"au {'1er' if when.month <= 6 else '2e'} semestre {when.year}{unsure}"
    return f"en {when.year}{unsure}"


def pick(what: str) -> str:
    plain = normalize(what or "")
    return next((key for key in SATELLITES if key in plain), "iss")


class ShowSpaceTool(Tool):
    name = "show_space"
    description = (
        "MONTRE sur le globe où est la station spatiale (ISS), la station chinoise Tiangong ou "
        "le télescope Hubble, en direct, avec sa trajectoire, et ses prochains passages "
        "VISIBLES à l'œil nu depuis chez l'utilisateur (« montre-moi l'ISS », « où est la "
        "station spatiale ? », « quand passe l'ISS au-dessus de chez moi ? »)."
    )
    parameters = {
        "what": {"type": "string", "enum": ["ISS", "Tiangong", "Hubble"],
                 "description": "Ce qui est demandé (ISS si rien de précis)"},
    }  # fmt: skip

    def __init__(self, home_city: str = "", client: httpx.Client | None = None) -> None:
        self.home_city = home_city
        self.client = client or httpx.Client(timeout=20, headers=HEADERS)
        self._home: list[float] | None = None

    def label(self, args: dict) -> str:
        return f"🛰️ Espace : {args.get('what') or 'ISS'}"

    def home(self) -> list[float] | None:
        """[lon, lat] de chez l'utilisateur (cherché une fois)."""
        if self._home is None and self.home_city:
            found = find_place(self.client, self.home_city)
            if found:
                self._home = [float(found["lon"]), float(found["lat"])]
        return self._home

    def run(self, what: str = "ISS") -> ToolResult:
        chosen, start = pick(what), now()
        try:
            orbits = {key: orbit(self.client, SATELLITES[key][0]) for key in SATELLITES}
        except Busy:
            return ToolResult(BUSY)
        sats = [{"label": SATELLITES[key][2], "focus": key == chosen, "step": 60,
                 "t0": -BEHIND * 60,
                 "track": track(sat, start - timedelta(minutes=BEHIND), BEHIND + AHEAD)}
                for key, sat in orbits.items()]  # fmt: skip
        lat, lon, alt, speed = where(orbits[chosen], start)
        name = SATELLITES[chosen][1]
        facts = (f"{name} survole en ce moment : {overflown(self.client, lat, lon)}, à "
                 f"{round(alt)} km d'altitude, à {round(speed, -2):.0f} km/h (un tour de la "
                 f"Terre en {round(2 * math.pi / orbits[chosen].no_kozai)} min)")  # fmt: skip
        home = self.home()
        if home:
            seen = passes(orbits[chosen], home[1], home[0], start, PASS_HOURS)
            today = start.astimezone()
            facts += (
                f". Prochains passages visibles à l'œil nu depuis {self.home_city} : "
                + " ; ".join(pass_text(p, today) for p in seen[:2])
                if seen
                else f". Aucun passage visible à l'œil nu depuis {self.home_city} dans les "
                "3 prochains jours"
            )
        data = {"sats": sats, "home": home, "pads": []}
        return ToolResult(
            f"Globe affiché, en direct : {facts}. Dis-le en deux ou trois phrases, en "
            "français naturel (« au-dessus du Canada »), sans rien inventer.",
            Display("space", f"Espace · {SATELLITES[chosen][2]}", data),
        )


class NextLaunchesTool(Tool):
    name = "next_launches"
    description = (
        "Les PROCHAINS LANCEMENTS de fusées, montrés sur le globe (« c'est quand le prochain "
        "lancement SpaceX ? », « les prochaines fusées », « prochain lancement d'Ariane »)."
    )
    parameters = {
        "who": {"type": "string",
                "description": "Opérateur ou fusée (SpaceX, Ariane, NASA…), vide = tous"},
    }  # fmt: skip

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=20, headers=HEADERS)

    def label(self, args: dict) -> str:
        return f"🚀 Lancements : {args.get('who') or 'tous'}"

    def run(self, who: str = "") -> ToolResult:
        try:
            found = launches(self.client, (who or "").strip())[:3]
        except Busy:
            return ToolResult(BUSY)
        if not found:
            return ToolResult(f"Dis EXACTEMENT : « Je ne trouve aucun lancement prévu pour "
                              f"{who}. »")  # fmt: skip
        today, lines, pads = now().astimezone(), [], []
        for item in found:
            when = datetime.fromisoformat(item["net"].replace("Z", "+00:00")).astimezone()
            precision = item["precision"]
            if precision in PRECISE and item["status"] == "TBD" and (
                when.astimezone(UTC).hour, when.minute) == (0, 0):  # fmt: skip
                precision = "Day"  # minuit pile, pas confirmé : l'heure n'est pas connue
            sure = "" if item["status"] == "Go" or precision not in PRECISE else " (à confirmer)"
            what = " de ".join(x for x in (item["rocket"], item["provider"]) if x)
            pad = f", depuis {item['pad']}" if item["pad"] else ""
            lines.append(f"{launch_date(when, precision, today)}{sure} : {what}, mission "
                         f"{item['mission']}{pad}")  # fmt: skip
            if item["where"]:
                day = f"{when.day} {MONTHS[when.month - 1]}"  # une date floue : la fusée seule
                label = f"{item['rocket']} · {day}" if precision in PRECISE else item["rocket"]
                pads.append({"where": item["where"], "label": label})
        return ToolResult(
            "Prochains lancements (heure de l'utilisateur), montrés sur le globe : "
            + " ; ".join(lines)
            + ". Dis le premier en une phrase (date, fusée, mission), puis cite les autres "
            "en bref. Rien d'inventé.",
            Display(
                "space", f"Lancements · {who or 'tous'}", {"sats": [], "home": None, "pads": pads}
            ),  # fmt: skip
        )
