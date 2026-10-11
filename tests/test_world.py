"""Veille monde (J9) : lecture des flux (titres, GDACS), thèmes reliés aux marchés, phrases
construites par le code, bloc des analyses, ligne du briefing, alerte discrète sans doublon."""

from datetime import UTC, datetime, timedelta

import httpx

from friday.app.notification import QUIET, notification
from friday.app.world_watch import WorldWatch
from friday.brain.router import SkillRouter
from friday.brain.skills import SKILLS
from friday.tools.world import MarketMoversTool, WorldNewsTool
from friday.trading.instruments import by_symbol
from friday.world.digest import World, describe
from friday.world.sources import (
    Disaster,
    Headline,
    WorldUnavailable,
    fetch_disasters,
    fetch_headlines,
)
from friday.world.themes import disaster_theme

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
RSS = """<rss><channel>
<item><title>EN DIRECT, guerre en Ukraine : frappes russes sur Kiev</title>
<pubDate>Sun, 11 Oct 2026 07:00:00 GMT</pubDate><description>Moscou a tiré…</description></item>
<item><title><![CDATA[L'Iran menace de fermer le détroit d'Ormuz]]></title>
<pubDate>Sun, 11 Oct 2026 06:00:00 GMT</pubDate><description>Le pétrole…</description></item>
<item><title>Un vieux titre sur la Fed</title>
<pubDate>Wed, 07 Oct 2026 06:00:00 GMT</pubDate></item>
</channel></rss>"""
GDACS = """<rss xmlns:gdacs="http://www.gdacs.org" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#">
<channel>{}</channel></rss>"""
ITEM = """<item><guid>{id}</guid><pubDate>Sun, 11 Oct 2026 08:00:00 GMT</pubDate>
<gdacs:dateadded>Sun, 11 Oct 2026 08:00:00 GMT</gdacs:dateadded>
<gdacs:iscurrent>true</gdacs:iscurrent><gdacs:eventtype>{kind}</gdacs:eventtype>
<gdacs:alertlevel>{level}</gdacs:alertlevel><gdacs:country>{country}</gdacs:country>
<gdacs:severity unit="M" value="{mag}">Magnitude</gdacs:severity>
<geo:Point><geo:lat>{lat}</geo:lat><geo:long>{lon}</geo:long></geo:Point></item>"""


def quake(id="EQ1", level="Orange", country="Japan", mag=7.2, lat=36.0, lon=140.0, kind="EQ"):
    return ITEM.format(id=id, kind=kind, level=level, country=country, mag=mag, lat=lat, lon=lon)


def fake_get(pages: dict):
    def get(url, **kwargs):
        for key, body in pages.items():
            if key in url:
                return httpx.Response(200, text=body, request=httpx.Request("GET", url))
        return httpx.Response(503, request=httpx.Request("GET", url))

    return get


def world(items=None, rss=RSS) -> World:
    items = (quake(),) if items is None else items
    get = fake_get({"lemonde": rss, "gdacs": GDACS.format("".join(items))})
    return World(lambda: fetch_headlines(get), lambda: fetch_disasters(get), now=lambda: NOW)


def test_sources_are_read_and_a_dead_feed_is_tolerated():
    get = fake_get({"lemonde": RSS})  # France 24 en panne : Le Monde suffit
    titles = fetch_headlines(get)
    assert len(titles) == 3 and titles[0].source == "Le Monde"
    assert titles[1].title == "L'Iran menace de fermer le détroit d'Ormuz"
    try:
        fetch_headlines(fake_get({}))
        raise AssertionError("aucune source : doit échouer")
    except WorldUnavailable as error:
        assert "indisponible" in str(error)
    (d,) = fetch_disasters(fake_get({"gdacs": GDACS.format(quake())}))
    assert (d.kind, d.level, d.country, d.magnitude, d.major) == (
        "EQ",
        "Orange",
        "Japan",
        7.2,
        True,
    )
    assert describe(d) == "séisme de magnitude 7,2 au Japon (alerte orange)"


def test_overview_is_built_by_the_code():
    spoken, items = world().overview()
    assert spoken.startswith("Dis EXACTEMENT : « Dans le monde : Guerre en Ukraine : frappes")
    assert "Un vieux titre" not in spoken  # plus de 24 h
    assert "Catastrophes en cours : séisme de magnitude 7,2 au Japon" in spoken
    assert items[0]["meta"].startswith("Le Monde")
    tool = WorldNewsTool(world())
    assert tool.run().display.data["icon"] == "🌍"


def test_market_movers_link_the_news_to_the_users_instruments():
    eurusd, gold, oil, jpy = (by_symbol(s) for s in ("EURUSD", "XAUUSD", "USOIL", "USDJPY"))
    said = world().movers([eurusd, gold])
    assert said.startswith("Dis EXACTEMENT : « Ce qui peut bouger EUR/USD et l'or. ")
    assert "Russie et Ukraine, pour l'euro, l'or et l'énergie" in said
    assert said.endswith("Ce n'est ni un signal ni un conseil. »")
    assert "le yen" in world().movers([jpy])  # le séisme au Japon
    assert "Moyen-Orient" in world().movers([oil]) and "Ormuz" in world().movers([oil])
    calm = world(items=(), rss="<rss><channel></channel></rss>").movers([eurusd])
    assert "Rien de marquant pour EUR/USD" in calm
    tool = MarketMoversTool(world(), lambda: [eurusd])
    assert "EUR/USD" in tool.run().text and "l'or" in tool.run("or").text


def test_claude_and_the_trading_briefing_get_the_world_too():
    block = world().context(by_symbol("USOIL"))
    assert "Ormuz" in block and "thème : Moyen-Orient" in block and "Kiev" not in block
    assert "Aucune actualité internationale" in world().context(by_symbol("NZDUSD"))
    line = world().briefing_line([by_symbol("EURUSD")])
    assert line.startswith("Monde, à surveiller : Russie et Ukraine")
    offline = World(lambda: (_ for _ in ()).throw(WorldUnavailable("hors ligne")),
                    lambda: [], now=lambda: NOW)  # fmt: skip
    assert offline.briefing_line([by_symbol("EURUSD")]) == ""


def test_only_gulf_of_mexico_cyclones_touch_oil():
    def cyclone(lat, lon):
        return Disaster("TC1", "TC", "Red", "Mexico", None, NOW, lat, lon)

    assert disaster_theme(cyclone(25.0, -90.0)).name == "pétrole et OPEP"
    assert disaster_theme(cyclone(17.6, -104.8)) is None  # côté Pacifique


def test_a_major_event_is_a_quiet_notification_given_once(tmp_path):
    sent = []
    items = (quake(), quake("EQ2", "Green", "Chile", 5.1), quake("TC9", "Red", "Mexico", 0,
             25.0, -90.0, "TC"))  # fmt: skip
    watch = WorldWatch(world(items), tmp_path / "vu.json", lambda task, r: sent.append((task, r)))
    assert watch.check() == 2 and watch.check() == 0  # pas deux fois
    task, result = sent[0]
    assert task == "monde" and task in QUIET
    assert result.text == ("Dis EXACTEMENT : « Alerte monde : séisme de magnitude 7,2 au Japon "
                           "(alerte orange). Ça peut faire bouger le yen. »")  # fmt: skip
    assert notification(task, result).data["text"].startswith("Alerte monde : séisme")
    old = World(lambda: [], lambda: [Disaster("EQ3", "EQ", "Red", "Peru", 7.5,
                NOW - timedelta(days=2), 0, 0)], now=lambda: NOW)  # fmt: skip
    assert WorldWatch(old, tmp_path / "v2.json", lambda *a: sent.append(a)).check() == 0


def test_the_cache_keeps_an_old_copy_when_the_source_fails():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) > 1:
            raise WorldUnavailable("panne")
        return [Headline(NOW, "Titre", "", "Le Monde")]

    clock = [NOW]
    w = World(flaky, lambda: [], now=lambda: clock[0])
    assert len(w.headlines()) == 1
    clock[0] = NOW + timedelta(minutes=20)  # copie périmée, source en panne : on la garde
    assert len(w.headlines()) == 1 and len(calls) == 2


def test_routing_world_requests():
    choose = SkillRouter(SKILLS).choose
    for text in ("quoi de neuf dans le monde ?", "il y a eu un séisme ?",
                 "qu'est-ce qui peut bouger les marchés aujourd'hui ?"):  # fmt: skip
        assert "monde" in choose(text), text
    assert "monde" not in choose("quel temps fait-il demain ?")


def test_the_code_chooses_market_movers_and_its_instrument():
    from friday.tools.world import world_request

    assert world_request("qu'est-ce qui peut bouger les marchés aujourd'hui ?") == (
        "market_movers", {"instrument": ""})  # fmt: skip
    assert world_request("quoi de neuf pour l'or ?") == ("market_movers", {"instrument": "l'or"})
    assert world_request("quoi de neuf pour ce soir ?") is None  # pas un marché
    assert world_request("quel est le cours de l'or ?") is None
    assert world_request("quoi de neuf dans le monde ?") == ("world_news", {})
    assert world_request("quel est le plus haut immeuble dans le monde ?") is None


def test_titles_are_easy_to_repeat():
    from friday.world.digest import _title

    long = Headline(NOW, "EN DIRECT, guerre : Trump réclame « un nouveau président » " + "x" * 200,
                    "", "Le Monde")  # fmt: skip
    title = _title(long)
    assert title.startswith("Guerre : Trump réclame un nouveau président")
    assert "«" not in title and len(title) <= 121 and title.endswith("…")


def test_a_prefetched_ready_made_sentence_is_said_without_the_model():
    from fakes import SETTINGS, FakeClient

    from friday.brain.llm import Brain
    from friday.tools.base import ToolBox

    client = FakeClient(rounds=[["Je résume à ma façon…"]])
    tool = MarketMoversTool(world(), lambda: [by_symbol("EURUSD")])
    brain = Brain(SETTINGS, client=client, toolbox=ToolBox([tool]),
                  prefetch=lambda q: ("market_movers", {}))  # fmt: skip
    said = "".join(e for e in brain.reply("qu'est-ce qui peut bouger les marchés ?")
                   if isinstance(e, str))  # fmt: skip
    assert said.startswith("Ce qui peut bouger EUR/USD. ") and "résume" not in said
    assert not [c for c in client.calls if c.get("stream")]  # qwen n'a pas été appelé
    calm = World(lambda: [], lambda: [], now=lambda: NOW)
    brain = Brain(SETTINGS, client=FakeClient(rounds=[["Rien à signaler."]]),
                  toolbox=ToolBox([WorldNewsTool(calm)]),
                  prefetch=lambda q: ("world_news", {}))  # fmt: skip
    said = "".join(e for e in brain.reply("quoi de neuf ?") if isinstance(e, str))
    assert said == "Je n'ai aucun titre international récent."


def test_the_globe_shows_themes_and_disasters():
    from friday.tools.world import ShowWorldTool, world_request
    from friday.ui.desktop.scenes.map_scene import page, world_script
    from friday.world.globe import globe

    spoken, data = globe(world(), [by_symbol("EURUSD")])
    kinds = {p["label"]: p["kind"] for p in data["points"]}
    assert kinds["Russie et Ukraine"] == "mine"  # touche l'EUR/USD : couleur de l'interface
    assert kinds["Moyen-Orient"] == "theme" and kinds["Séisme 7,2"] == "orange"
    assert spoken == (  # Russie-Ukraine, Moyen-Orient, pétrole, Japon (le séisme)
        "Dis EXACTEMENT : « Voici le monde en ce moment : 4 sujets dans l'actualité, dont 1 "
        "pour EUR/USD, plus 1 catastrophe en cours. »")  # fmt: skip
    result = ShowWorldTool(world(), lambda: [by_symbol("EURUSD")]).run()
    assert result.display.kind == "world" and result.display.data == data
    assert world_script(data).startswith("window.fridayWorld && window.fridayWorld([{")
    html = page("#f0a83c")
    assert "maplibre-gl@5" in html and 'type: "globe"' in html  # MapLibre 5 : le globe
    assert "__" not in html.replace("__proto__", "")  # tout est remplacé
    assert "setCallouts(points)" in html and "spinGlobe()" in html  # étiquettes, rotation
    assert world_request("montre-moi ce qui se passe dans le monde") == ("show_world", {})
    empty = World(lambda: [], lambda: [], now=lambda: NOW)
    assert "Rien de marquant" in globe(empty, [])[0]


ROUNDUP_RSS = """<rss><channel>
<item><title>Colère lycéenne, trois ans du 7-Octobre : la semaine en images</title>
<pubDate>Sun, 11 Oct 2026 08:30:00 GMT</pubDate><description>Gaza, Israël…</description></item>
<item><title>Gaza : nouvelles frappes israéliennes</title>
<pubDate>Sun, 11 Oct 2026 07:30:00 GMT</pubDate><description>Le Hamas…</description></item>
<item><title>Le prix du baril recule</title>
<pubDate>Sun, 11 Oct 2026 07:00:00 GMT</pubDate><description>Israël et l'Iran…</description></item>
</channel></rss>"""


def test_a_named_instrument_gets_its_own_answer():
    """Constaté : « quoi de neuf pour l'or ? » = la réponse de « qu'est-ce qui peut bouger les
    marchés ? », avec un récapitulatif « la semaine en images » comme titre."""
    gold = by_symbol("XAUUSD")
    news = world(items=(), rss=ROUNDUP_RSS)
    said = news.movers([gold], named=True)
    assert said.startswith("Dis EXACTEMENT : « Pour l'or, à surveiller dans l'actualité. ")
    middle_east = said.split("Moyen-Orient : ")[1]
    assert middle_east.startswith("Gaza : nouvelles frappes israéliennes ; Le prix du baril")
    assert "en images" not in said  # deux vrais titres passent avant le récapitulatif
    assert "pour le pétrole et l'or" not in said
    general = news.movers([gold])  # ses marchés, sans en nommer un : la phrase habituelle
    assert general.startswith("Dis EXACTEMENT : « Ce qui peut bouger l'or. ")
    tool = MarketMoversTool(news, lambda: [gold, by_symbol("EURUSD")])
    assert "Pour l'or, à surveiller" in tool.run("or").text
    assert "Ce qui peut bouger l'or et EUR/USD" in tool.run().text


def test_emojis_and_cut_titles_read_cleanly():
    """Constaté : « 🔴 Donald Trump affirme… » (France 24) ; « …. » après un titre coupé."""
    from friday.world.digest import _title

    head = Headline(NOW, "🔴 Donald Trump affirme qu'un accord est proche", "", "France 24")
    assert _title(head) == "Donald Trump affirme qu'un accord est proche"
    rss = RSS.replace("L'Iran menace de fermer le détroit d'Ormuz", "L'Iran " + "très " * 40)
    said = world(items=(), rss=rss).movers([by_symbol("USOIL")], named=True)
    assert "…." not in said and "… Ce n'est ni un signal" in said
