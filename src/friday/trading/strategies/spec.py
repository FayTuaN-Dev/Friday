"""Le format des règles d'un plan écrit, une fois traduit (par Claude, après aperçu) : du JSON
que le CODE vérifie avant de s'en servir, et qu'il redit en français (« ce que Friday a
compris »). Rien n'est exécuté d'autre que ces conditions sur des indicateurs.

{"nom", "resume", "unite": "heure" | "jour"  (bougies d'une heure, ou journalières : les
 périodes sont alors en jours, comme les Turtles),
 "tendance": {"ema": 200} | null, "achat": [conditions], "vente": [...],
 "stop": {"type": "atr", "multiple": 1.5, "journalier": false, "periode": 20}
         | {"type": "creux", "bougies": 10},
 "objectif": {"type": "r", "valeur": 2} | {"type": "indicateur", "indicateur": opérande}
             | {"type": "aucun"}  (on laisse courir : il faut alors une sortie),
 "sortie": {"bougies": 480} | null  (sortie suiveuse : cassure inverse du plus bas / plus haut
           des N bougies précédentes, comme les Turtles),
 "heures": [9, 18] | null, "non_traduit": ["…"]}
condition : {"gauche": opérande, "op": OP, "droite": opérande, "k": 1}
opérande  : {"indicateur": INDICATEUR, "periode": 14, "ecarts": 2, "decalage": 0} | {"valeur": 30}
"""

INDICATORS = {  # nom : (en français, a une période ?)
    "cours": ("le cours (clôture)", False), "ouverture": ("l'ouverture", False),
    "haut": ("le plus haut de la bougie", False), "bas": ("le plus bas de la bougie", False),
    "ema": ("l'EMA", True), "sma": ("la moyenne simple", True), "rsi": ("le RSI", True),
    "atr": ("l'ATR", True), "bollinger_haute": ("la bande de Bollinger haute", True),
    "bollinger_basse": ("la bande de Bollinger basse", True),
    "plus_haut": ("le plus haut des bougies précédentes", True),
    "plus_bas": ("le plus bas des bougies précédentes", True),
}  # fmt: skip
OPS = {">": "est au-dessus de", "<": "est en dessous de", ">=": "est au moins à",
       "<=": "est au plus à", "croise_au_dessus": "croise au-dessus de",
       "croise_en_dessous": "croise en dessous de", "proche": "est proche de",
       "monte": "monte", "baisse": "baisse"}  # fmt: skip
ALONE = {"monte", "baisse"}  # sans opérande de droite
MAX_CONDITIONS = 8
# En bougies d'une heure : ~62 jours. Constaté : Turtle Traders (cassure des 55 jours) traduit
# en 1 320 bougies, refusé à 400. Les alertes et la check-list lisent donc 6 mois de bougies.
MAX_PERIOD = 1500


NOTE_CHARS = 400  # constaté : à 200, les notes de Turtle Traders coupées en plein mot


def short(text: str, limit: int = NOTE_CHARS) -> str:
    """Une note du traducteur, coupée entre deux mots si elle est trop longue."""
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


class SpecError(ValueError):
    """Message pour l'utilisateur."""


def _operand(data, where: str) -> dict:
    if not isinstance(data, dict):
        raise SpecError(f"{where} : opérande manquante")
    if "valeur" in data:
        if not isinstance(data["valeur"], int | float):
            raise SpecError(f"{where} : valeur non numérique")
        return {"valeur": float(data["valeur"])}
    name = data.get("indicateur")
    if name not in INDICATORS:
        raise SpecError(f"{where} : indicateur inconnu « {name} »")
    out = {"indicateur": name, "decalage": int(data.get("decalage", 0))}
    if INDICATORS[name][1]:
        period = int(data.get("periode", 14))
        if not 1 <= period <= MAX_PERIOD:
            raise SpecError(f"{where} : période hors limites ({period})")
        out["periode"] = period
    if name.startswith("bollinger"):
        out["ecarts"] = float(data.get("ecarts", 2))
    if not 0 <= out["decalage"] <= 50:
        raise SpecError(f"{where} : décalage hors limites")
    return out


def _condition(data, where: str) -> dict:
    if not isinstance(data, dict) or data.get("op") not in OPS:
        found = data.get("op") if isinstance(data, dict) else data
        raise SpecError(f"{where} : opérateur inconnu « {found} »")
    out = {"op": data["op"], "gauche": _operand(data.get("gauche"), where)}
    if data["op"] not in ALONE:
        out["droite"] = _operand(data.get("droite"), where)
    if data["op"] == "proche":
        out["k"] = float(data.get("k", 1.0))
    return out


def validate(data) -> dict:
    """Le plan traduit, nettoyé ; SpecError si quelque chose ne tient pas."""
    if not isinstance(data, dict):
        raise SpecError("la traduction n'est pas un objet JSON")
    try:
        return _validate(data)
    except (TypeError, ValueError, KeyError, IndexError) as error:
        if isinstance(error, SpecError):
            raise
        raise SpecError(f"règle mal formée ({error})") from error


def _bounded(value, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _validate(data: dict) -> dict:
    trend, stop = data.get("tendance"), data.get("stop") or {}
    target, hours = data.get("objectif") or {}, data.get("heures")
    spec = {
        "nom": str(data.get("nom") or "Mon plan")[:60],
        "resume": str(data.get("resume") or "")[:300],
        "unite": "jour" if data.get("unite") == "jour" else "heure",
        "tendance": {"ema": int(trend["ema"])} if isinstance(trend, dict) and trend.get("ema")
        else None,
    }  # fmt: skip
    for side in ("achat", "vente"):
        conditions = data.get(side) or []
        if not isinstance(conditions, list) or len(conditions) > MAX_CONDITIONS:
            raise SpecError(f"{side} : liste de conditions invalide")
        spec[side] = [_condition(c, f"{side} n°{n + 1}") for n, c in enumerate(conditions)]
    if not spec["achat"] and not spec["vente"]:
        raise SpecError("aucune condition d'entrée")
    if stop.get("type") == "creux":
        spec["stop"] = {"type": "creux", "bougies": int(_bounded(stop.get("bougies", 10), 2, 100))}
    else:
        spec["stop"] = {"type": "atr", "multiple": _bounded(stop.get("multiple", 1.5), 0.1, 20)}
        if stop.get("journalier"):  # « 2 N » des Turtles : l'ATR des 20 derniers JOURS
            days = int(_bounded(stop.get("periode", 20), 2, 100))
            spec["stop"] |= {"journalier": True, "periode": days}
    exit_rule = data.get("sortie")
    spec["sortie"] = ({"bougies": int(_bounded(exit_rule.get("bougies", 240), 2, MAX_PERIOD))}
                      if isinstance(exit_rule, dict) else None)  # fmt: skip
    if target.get("type") == "aucun":
        if spec["sortie"] is None:
            raise SpecError("objectif « aucun » sans sortie : le trade ne finirait jamais")
        spec["objectif"] = {"type": "aucun"}
    elif target.get("type") == "indicateur":
        level = _operand(target.get("indicateur"), "objectif")
        spec["objectif"] = {"type": "indicateur", "indicateur": level}
    else:
        spec["objectif"] = {"type": "r", "valeur": _bounded(target.get("valeur", 2), 0.3, 20)}
    valid_hours = isinstance(hours, list) and len(hours) == 2
    daily = spec["unite"] == "jour"  # une journée n'a pas d'heure de clôture à choisir
    spec["heures"] = [int(hours[0]), int(hours[1])] if valid_hours and not daily else None
    spec["non_traduit"] = [short(str(x)) for x in data.get("non_traduit") or []][:12]
    return spec


def say_operand(o: dict) -> str:
    if "valeur" in o:
        return f"{o['valeur']:g}".replace(".", ",")
    name, has_period = INDICATORS[o["indicateur"]]
    if o["indicateur"] in ("plus_haut", "plus_bas"):  # « des 24 bougies précédentes »
        text = name.replace("des bougies", f"des {o['periode']} bougies")
    else:
        text = name + (f" {o['periode']}" if has_period else "")
    if o["indicateur"].startswith("bollinger"):
        text += f" ({o['ecarts']:g} écarts)".replace(".", ",")
    if o.get("decalage"):
        text += f" d'il y a {o['decalage']} bougie(s)"
    return text


def say_condition(c: dict) -> str:
    left, op = say_operand(c["gauche"]), OPS[c["op"]]
    if c["op"] in ALONE:
        return f"{left} {op}"
    near = f" (à moins de {c['k']:g} ATR)".replace(".", ",") if c["op"] == "proche" else ""
    text = f"{left} {op} {say_operand(c['droite'])}{near}"
    return text.replace(" de le ", " du ").replace(" de les ", " des ")


def describe(spec: dict) -> list[str]:
    """Ce que Friday a compris, ligne par ligne, en français."""
    lines = []
    in_days = spec.get("unite") == "jour"
    if in_days:
        lines.append("Bougies : journalières (les périodes sont en jours)")
    if spec["tendance"]:
        lines.append(f"Tendance : achats seulement au-dessus de l'EMA {spec['tendance']['ema']} "
                     "journalière, ventes seulement en dessous")  # fmt: skip
    for side in ("achat", "vente"):
        if spec[side]:
            lines.append(f"{side.capitalize()} quand : " + " ; ".join(
                say_condition(c) for c in spec[side]))  # fmt: skip
    stop = spec["stop"]
    daily = ""
    if stop.get("journalier"):
        daily = f" journaliers (ATR des {stop['periode']} derniers jours)"
    lines.append(f"Stop : {stop['multiple']:g} ATR{daily}".replace(".", ",")
                 if stop["type"] == "atr"
                 else f"Stop : sous le dernier creux (au-dessus du dernier sommet en vente) des "
                      f"{stop['bougies']} dernières bougies")  # fmt: skip
    target = spec["objectif"]
    lines.append("Objectif : aucun, on laisse courir la tendance" if target["type"] == "aucun"
                 else f"Objectif : {target['valeur']:g} fois le risque".replace(".", ",")
                 if target["type"] == "r"
                 else f"Objectif : {say_operand(target['indicateur'])}")  # fmt: skip
    if spec.get("sortie"):
        lines.append(f"Sortie : à la cassure du plus bas des {spec['sortie']['bougies']} bougies "
                     "précédentes (du plus haut en vente), qui suit le prix")  # fmt: skip
    if spec["heures"]:
        lines.append(f"Heures : entrées sur les bougies qui ferment entre {spec['heures'][0]} h "
                     f"et {spec['heures'][1]} h (Paris)")  # fmt: skip
    if in_days:  # « des 20 bougies précédentes » → « des 20 jours précédents »
        for a, b in DAY_WORDS:
            lines = [line.replace(a, b) for line in lines]
    lines += [f"À noter : {x}" for x in spec["non_traduit"]]
    return lines


DAY_WORDS = (("bougies précédentes", "jours précédents"), ("dernières bougies", "derniers jours"),
             ("bougie(s)", "jour(s)"))  # fmt: skip
