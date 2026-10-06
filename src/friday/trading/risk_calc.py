"""Calculs de risque forex, déterministes (jamais confiés au modèle).

Conventions : 1 lot standard = 100 000 unités de la devise de base ; un pip vaut 0,0001
(0,01 pour les paires en yen). Les tailles de position sont arrondies vers le BAS au
centième de lot (micro-lot) : on ne risque jamais plus que prévu.
"""

import math
from dataclasses import dataclass

LOT_UNITS = 100_000


class MissingRate(ValueError):
    """Il manque un cours pour convertir dans la devise du compte (message pour l'utilisateur)."""


def split_pair(pair: str) -> tuple[str, str]:
    letters = "".join(c for c in pair.upper() if c.isalpha())
    if len(letters) != 6:
        raise ValueError(f"Paire inconnue : « {pair} » (ex. EUR/USD).")
    return letters[:3], letters[3:]


def pip_size(pair: str) -> float:
    return 0.01 if split_pair(pair)[1] == "JPY" else 0.0001


def pip_value(
    pair: str, lots: float, account: str, price: float | None = None,
    quote_to_account: float | None = None,
) -> float:  # fmt: skip
    """Valeur d'un pip pour `lots`, dans la devise du compte.

    `price` : cours de la paire (nécessaire si le compte est dans la devise de base) ;
    `quote_to_account` : 1 unité de la devise de cotation en devise du compte (autres cas).
    """
    base, quote = split_pair(pair)
    in_quote = lots * LOT_UNITS * pip_size(pair)
    account = account.upper()
    if quote == account:
        return in_quote
    if base == account:
        if not price:
            raise MissingRate(f"Il me faut le cours actuel de {base}/{quote}.")
        return in_quote / price
    if not quote_to_account:
        raise MissingRate(f"Il me faut le cours {quote}/{account} pour convertir.")
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
        raise ValueError("Stop (en pips) et valeur du pip positifs attendus.")
    allowed = max_loss(capital, risk_percent)
    lots = math.floor(allowed / (stop_pips * pip_value_per_lot) * 100 + 1e-9) / 100
    return PositionSize(lots, lots * stop_pips * pip_value_per_lot, allowed)


@dataclass
class RiskReward:
    direction: str  # « achat » ou « vente »
    risk_pips: float
    reward_pips: float
    ratio: float  # gain potentiel / perte potentielle


def risk_reward(pair: str, entry: float, stop: float, target: float) -> RiskReward:
    if stop == entry or target == entry:
        raise ValueError("Le stop et l'objectif doivent différer du prix d'entrée.")
    if (stop < entry) != (target > entry):
        raise ValueError("Stop et objectif doivent être de part et d'autre de l'entrée.")
    size = pip_size(pair)
    risk, reward = abs(entry - stop) / size, abs(target - entry) / size
    return RiskReward("achat" if target > entry else "vente", risk, reward, reward / risk)


def result_in_r(entry: float, stop: float, exit_price: float) -> float:
    """Résultat d'un trade en multiples du risque initial (R) : +2 = deux fois le risque."""
    risk = entry - stop
    if risk == 0:
        raise ValueError("Stop égal à l'entrée : risque nul.")
    return (exit_price - entry) / risk
