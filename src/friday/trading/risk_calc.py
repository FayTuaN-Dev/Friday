"""Calculs de risque, déterministes (jamais confiés au modèle), pour tout instrument : forex,
métaux, matières premières, indices, crypto, actions (voir instruments.py).

Conventions : la taille d'un lot et d'un pip / point vient de la fiche de l'instrument
(forex : 100 000 unités et 0,0001 ; or : 100 onces et 0,1 $ ; action : 1 titre et 0,01).
Les tailles de position sont arrondies vers le BAS au centième de lot : on ne risque jamais
plus que prévu.
"""

import math
from dataclasses import dataclass

from friday.trading.instruments import Instrument, by_symbol, detect


class MissingRate(ValueError):
    """Il manque un cours pour convertir dans la devise du compte (message pour l'utilisateur)."""


def resolve(instrument: Instrument | str) -> Instrument:
    if isinstance(instrument, Instrument):
        return instrument
    found = detect(instrument) or by_symbol(instrument)  # « l'or », « EUR/USD », « AAPL »
    if found is None:
        raise ValueError(f"Instrument inconnu : « {instrument} » (ex. EUR/USD, XAUUSD, AAPL).")
    return found


def split_pair(pair: str) -> tuple[str, str]:
    """Devise de base et de cotation d'une paire forex."""
    instrument = resolve(pair)
    if instrument.kind != "forex":
        raise ValueError(f"« {pair} » n'est pas une paire de devises.")
    return instrument.symbol[:3], instrument.symbol[3:]


def pip_size(instrument: Instrument | str) -> float:
    return resolve(instrument).pip


def pip_value(
    instrument: Instrument | str, lots: float, account: str, price: float | None = None,
    quote_to_account: float | None = None,
) -> float:  # fmt: skip
    """Valeur d'un pip / point pour `lots`, dans la devise du compte.

    `price` : cours de l'instrument (nécessaire en forex si le compte est dans la devise de
    base) ; `quote_to_account` : 1 unité de la devise de cotation en devise du compte.
    """
    i = resolve(instrument)
    in_quote = lots * i.contract * i.pip
    account = account.upper()
    if i.quote == account:
        return in_quote
    if i.kind == "forex" and i.symbol[:3] == account:
        if not price:
            raise MissingRate(f"Il me faut le cours actuel de {i.name}.")
        return in_quote / price
    if not quote_to_account:
        raise MissingRate(f"Il me faut le cours {i.quote}/{account} pour convertir.")
    return in_quote * quote_to_account


def max_loss(capital: float, risk_percent: float) -> float:
    if capital <= 0 or not 0 < risk_percent <= 100:
        raise ValueError("Capital positif et risque entre 0 et 100 % attendus.")
    return capital * risk_percent / 100


@dataclass
class PositionSize:
    lots: float
    risked: float  # perte si le stop est touché, avec la taille arrondie
    max_loss: float  # perte maximale acceptée


def position_size(
    capital: float, risk_percent: float, stop_pips: float, pip_value_per_lot: float
) -> PositionSize:
    if stop_pips <= 0 or pip_value_per_lot <= 0:
        raise ValueError("Stop (en pips / points) et valeur du pip positifs attendus.")
    allowed = max_loss(capital, risk_percent)
    lots = math.floor(allowed / (stop_pips * pip_value_per_lot) * 100 + 1e-9) / 100
    return PositionSize(lots, lots * stop_pips * pip_value_per_lot, allowed)


def stop_in_pips(instrument: Instrument | str, entry: float, stop: float) -> float:
    """Distance entre l'entrée et le stop, en pips / points de l'instrument."""
    return abs(entry - stop) / resolve(instrument).pip


@dataclass
class RiskReward:
    direction: str  # « achat » ou « vente »
    risk_pips: float
    reward_pips: float
    ratio: float  # gain potentiel / perte potentielle


def risk_reward(
    instrument: Instrument | str, entry: float, stop: float, target: float
) -> RiskReward:
    if stop == entry or target == entry:
        raise ValueError("Le stop et l'objectif doivent différer du prix d'entrée.")
    if (stop < entry) != (target > entry):
        raise ValueError("Stop et objectif doivent être de part et d'autre de l'entrée.")
    size = pip_size(instrument)
    risk, reward = abs(entry - stop) / size, abs(target - entry) / size
    return RiskReward("achat" if target > entry else "vente", risk, reward, reward / risk)


def result_in_r(entry: float, stop: float, exit_price: float) -> float:
    """Résultat d'un trade en multiples du risque initial (R) : +2 = deux fois le risque."""
    risk = entry - stop
    if risk == 0:
        raise ValueError("Stop égal à l'entrée : risque nul.")
    return (exit_price - entry) / risk
