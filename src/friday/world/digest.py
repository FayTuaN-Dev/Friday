"""La veille monde (J9) : titres internationaux et catastrophes en cours, gardés 15 min ; les
phrases sont construites ici, par le code (le modèle n'a qu'à les répéter) : le point sur le
monde, ce qui peut bouger les marchés de l'utilisateur, le bloc joint aux analyses de Claude,
la ligne du briefing trading, et les événements majeurs à annoncer de soi-même."""

import re
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from friday.trading.instruments import Instrument
from friday.voice.wake import normalize
from friday.world.sources import (
    KINDS,
    LEVELS,
    Disaster,
    Headline,
    WorldUnavailable,
    fetch_disasters,
    fetch_headlines,
)
from friday.world.themes import Theme, disaster_theme, themes_of, where

TTL = timedelta(minutes=15)
RECENT = timedelta(hours=24)
MAX_TITLES, MAX_DISASTERS, MAX_THEMES = 4, 3, 3
MAX_CHARS = 120  # un titre lu à voix haute
ORDER = {"Red": 0, "Orange": 1, "Green": 2}
# Un récapitulatif (« la semaine en images ») cite tout et ne parle de rien : en dernier
ROUNDUP = re.compile(r"\b(?:en images|la semaine|en bref|resume de)\b")
# Émojis et pictogrammes des titres : ni lus ni affichés
SYMBOLS = re.compile(r"[^\w\s,.;:!?'’()\-–—…%€$&/+]")
ICONS = {"EQ": "🌐", "TC": "🌀", "FL": "🌊", "VO": "🌋", "WF": "🔥", "DR": "☀️"}


def describe(d: Disaster) -> str:
    """« séisme de magnitude 6,4 au Japon (alerte orange) »."""
    size = f" de magnitude {d.magnitude:g}".replace(".", ",") if d.magnitude else ""
    return f"{KINDS[d.kind]}{size} {where(d.country)} (alerte {LEVELS.get(d.level, d.level)})"


def names(instruments: list[Instrument]) -> str:
    found = [i.name for i in instruments]
    return " et ".join([", ".join(found[:-1]), found[-1]]) if len(found) > 1 else found[0]


def _title(h: Headline) -> str:
    """Sans « EN DIRECT, », guillemets ni point final, 120 caractères au plus : qwen ne
    répétait plus une phrase pleine de guillemets imbriqués (il la résumait, constaté)."""
    title = re.sub(r"^(?:en direct|live)\s*[,:-]\s*", "", h.title, flags=re.I)
    title = re.sub(r"[«»“”\"]\s?", "", title).rstrip(" .")
    title = " ".join(SYMBOLS.sub(" ", title).split())  # « 🔴 Donald Trump… » (France 24)
    if len(title) > MAX_CHARS:
        title = title[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return title[:1].upper() + title[1:]


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]  # « politique américaine » en début de phrase


def _said(text: str) -> str:
    """La phrase à répéter, sans « …. » après un titre coupé."""
    text = f"{text}. Ce n'est ni un signal ni un conseil.".replace("….", "…")
    return f"Dis EXACTEMENT : « {text} »"


class World:
    def __init__(self, headlines=fetch_headlines, disasters=fetch_disasters,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:  # fmt: skip
        self.fetchers = {"titres": headlines, "catastrophes": disasters}
        self.now = now
        self._cache: dict[str, tuple[datetime, list]] = {}
        self._lock = threading.Lock()

    def _get(self, name: str) -> list:
        """Les données (gardées 15 min) ; une vieille copie si la source ne répond plus."""
        with self._lock:
            kept = self._cache.get(name)
            if kept and self.now() - kept[0] < TTL:
                return kept[1]
            try:
                data = self.fetchers[name]()
            except WorldUnavailable:
                if kept:
                    return kept[1]
                raise
            self._cache[name] = (self.now(), data)
            return data

    def headlines(self) -> list[Headline]:
        """Les titres des dernières 24 h, du plus récent au plus ancien, sans doublon."""
        now, seen, found = self.now(), set(), []
        for h in sorted(self._get("titres"), key=lambda h: h.time, reverse=True):
            key = normalize(h.title)[:50]
            if now - h.time <= RECENT and key not in seen:
                seen.add(key)
                found.append(h)
        return found

    def disasters(self) -> list[Disaster]:
        """Les catastrophes en cours qui comptent : alerte orange ou rouge, gros séismes."""
        found = [
            d
            for d in self._get("catastrophes")
            if d.level in ("Red", "Orange") or (d.kind == "EQ" and (d.magnitude or 0) >= 6.5)
        ]
        return sorted(found, key=lambda d: (ORDER.get(d.level, 3), -d.time.timestamp()))

    # --- ce que Friday dit ---

    def overview(self) -> tuple[str, list[dict]]:
        """(phrase à dire, lignes à afficher) : le point sur le monde."""
        titles = self.headlines()
        try:
            disasters = self.disasters()
        except WorldUnavailable:
            disasters = []
        if not titles:
            return "Dis EXACTEMENT : « Je n'ai aucun titre international récent. »", []
        spoken = "Dans le monde : " + ". ".join(_title(h) for h in titles[:MAX_TITLES]) + "."
        if disasters:
            spoken += " Catastrophes en cours : " + " ; ".join(
                describe(d) for d in disasters[:MAX_DISASTERS]) + "."  # fmt: skip
        items = [{"text": h.title, "meta": f"{h.source} · {h.time.astimezone():%H:%M}",
                  "url": h.link} for h in titles[:10]]  # fmt: skip
        items += [
            {
                "text": f"{ICONS.get(d.kind, '⚠️')} {describe(d)}",
                "meta": f"GDACS · {d.time.astimezone():%d/%m %H:%M}",
            }
            for d in disasters[:6]
        ]
        return f"Dis EXACTEMENT : « {spoken} »", items

    def themes(self, instruments: list[Instrument] | None) -> list[tuple[Theme, list[str]]]:
        """Les thèmes du moment qui touchent ces instruments (tous si None), chacun avec ses
        titres et catastrophes, les plus présents d'abord."""
        ranked: dict[str, tuple[Theme, list[tuple[int, str]]]] = {}
        for h in self.headlines():
            # D'abord les titres qui parlent du thème, puis ceux où il n'est que dans le résumé
            # (constaté : « …la semaine en images » donné pour le Moyen-Orient et pour l'or)
            in_title = {t.name for t in themes_of(h.title)}
            roundup = bool(ROUNDUP.search(normalize(h.title)))
            for theme in themes_of(f"{h.title} {h.summary}"):
                rank = 2 if roundup else 0 if theme.name in in_title else 1
                ranked.setdefault(theme.name, (theme, []))[1].append((rank, _title(h)))
        found = {name: (theme, [title for _, title in sorted(items, key=lambda i: i[0])])
                 for name, (theme, items) in ranked.items()}  # fmt: skip
        try:
            for d in self.disasters():
                if theme := disaster_theme(d):
                    found.setdefault(theme.name, (theme, []))[1].insert(0, describe(d))
        except WorldUnavailable:
            pass
        kept = [
            (t, items)
            for t, items in found.values()
            if instruments is None or any(t.concerns(i) for i in instruments)
        ]
        return sorted(kept, key=lambda pair: -len(pair[1]))

    def movers(self, instruments: list[Instrument] | None, named: bool = False) -> str:
        """Ce qui peut bouger les marchés de l'utilisateur, d'après l'actualité ; `named` :
        un instrument nommé (« quoi de neuf pour l'or ? »), la réponse est centrée sur lui."""
        who = names(instruments) if instruments else "les marchés"
        themes = self.themes(instruments)[:MAX_THEMES]
        if not themes:
            return (f"Dis EXACTEMENT : « Rien de marquant pour {who} dans l'actualité "
                    "internationale des dernières 24 h. »")  # fmt: skip
        if named and instruments:  # « quoi de neuf pour l'or ? » : lui seul
            return self._about(instruments[0], themes)
        parts, used = [], set()
        for theme, items in themes:  # un titre différent pour chaque thème
            item = next((i for i in items if i not in used), items[0])
            used.add(item)
            parts.append(f"{_cap(theme.name)}, pour {theme.moves} : {item}")
        return _said(f"Ce qui peut bouger {who}. " + ". ".join(parts))

    @staticmethod
    def _about(instrument: Instrument, themes: list[tuple[Theme, list[str]]]) -> str:
        """Centré sur un instrument : deux titres par thème (constaté : la même réponse que
        « qu'est-ce qui peut bouger les marchés ? », « pour le pétrole et l'or » compris)."""
        parts, used = [], set()
        for theme, items in themes:
            fresh = [i for i in items if i not in used][:2] or items[:1]
            used.update(fresh)
            parts.append(f"{_cap(theme.name)} : " + " ; ".join(fresh))
        return _said(f"Pour {instrument.name}, à surveiller dans l'actualité. " + ". ".join(parts))

    def context(self, instrument: Instrument) -> str:
        """Le bloc joint aux analyses de Claude (titres de tiers liés à l'instrument)."""
        lines = []
        for h in self.headlines():
            linked = [t for t in themes_of(f"{h.title} {h.summary}") if t.concerns(instrument)]
            if linked:
                summary = h.summary[:200] + ("…" if len(h.summary) > 200 else "")
                lines.append(f"- {h.time.astimezone(UTC):%d/%m %H:%M} UTC · {h.source} · "
                             f"{h.title} — {summary} (thème : {linked[0].name})")  # fmt: skip
        try:
            disasters = self.disasters()
        except WorldUnavailable:
            disasters = []
        for d in disasters:
            theme = disaster_theme(d)
            if theme and theme.concerns(instrument):
                lines.append(f"- Catastrophe en cours : {describe(d)} (GDACS)")
        if not lines:
            return (f"Aucune actualité internationale liée à {instrument.name} dans les "
                    "dernières 24 h (Le Monde, France 24, GDACS).")  # fmt: skip
        return ("Actualité internationale liée, dernières 24 h (titres de tiers ; thèmes selon "
                "une grille fixe de Friday) :\n" + "\n".join(lines[:8]))  # fmt: skip

    def briefing_line(self, instruments: list[Instrument]) -> str:
        """La ligne « Monde » du briefing trading ; vide s'il n'y a rien (ou pas de réseau)."""
        try:
            themes = self.themes(instruments)[:MAX_THEMES]
        except WorldUnavailable:
            return ""
        if not themes:
            return ""
        return "Monde, à surveiller : " + " ; ".join(
            f"{t.name} ({t.moves})" for t, _ in themes) + "."  # fmt: skip

    def new_major(self, seen: set[str], within: timedelta) -> list[Disaster]:
        """Les événements majeurs récents pas encore annoncés."""
        now = self.now()
        return [d for d in self._get("catastrophes")
                if d.major and d.id not in seen and now - d.time <= within]  # fmt: skip
