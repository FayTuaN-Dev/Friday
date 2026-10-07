"""Les règles du plan de trading que le CODE vérifie (check-list avant trade), en chiffres.

Le plan rédigé (data/trading_plan.txt) sert à Claude ; ces réglages-ci, au calcul : gardés sur
le PC (data/trading_rules.json), modifiables dans Réglages → Trading. Les valeurs par défaut
reprennent le plan de départ (EMA200 journalière, repli sur l'EMA50 1 h, RSI 40–50, stop d'au
moins 1,5 ATR, 2 R, 1 %, 2 trades, 30 min avant une annonce forte).
"""

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class PlanRules:
    trend_ema: int = 200  # tendance : EMA journalière ; 0 = règle désactivée
    pullback_ema: int = 50  # entrée près de cette EMA 1 h ; 0 = règle désactivée
    pullback_atr: float = 1.0  # « près » : à moins de N × ATR 1 h
    rsi_low: float = 40  # zone du RSI 14 (1 h) à l'achat ; à la vente, la zone miroir (50–60)
    rsi_high: float = 50
    rsi_turning: bool = True  # le RSI doit repartir dans le sens du trade
    stop_atr: float = 1.5  # stop d'au moins N × ATR 1 h ; 0 = règle désactivée
    min_rr: float = 2.0  # objectif d'au moins N fois le risque ; 0 = règle désactivée
    max_risk: float = 1.0  # % du capital risqué au plus ; 0 = règle désactivée
    max_open: int = 2  # trades ouverts au plus (journal) ; 0 = règle désactivée
    news_minutes: int = 30  # pas d'entrée si une annonce forte tombe dans ce délai ; 0 = off
    capital: float = 0.0  # facultatif : capital du compte, pour vérifier le risque


def load_rules(path: Path | None) -> PlanRules:
    """Les règles enregistrées ; celles par défaut si le fichier manque ou est abîmé."""
    if path is None or not path.is_file():
        return PlanRules()
    try:
        data = json.loads(path.read_text("utf-8"))
        known = {f.name for f in fields(PlanRules)}
        return PlanRules(**{k: v for k, v in data.items() if k in known})
    except (OSError, ValueError, TypeError):
        log.warning("Règles du plan illisibles (%s) : valeurs par défaut", path)
        return PlanRules()


def save_rules(path: Path, rules: PlanRules) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(rules), indent=2, ensure_ascii=False), "utf-8")
