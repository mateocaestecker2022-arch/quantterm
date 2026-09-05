"""Signal « live » : direction courante (long/short/flat) d'une stratégie.

Outil d'aide à la décision — il **ne trade pas**. Il lit les dernières données,
calcule la position cible de la stratégie sur la barre la plus récente et affiche
la direction + les niveaux de stop/target (en ATR) à utiliser en cas d'entrée.

Pensé pour tourner en boucle sur un VPS (``signal ... --watch 60``) contre un
compte démo, avant tout passage en réel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import backtest, data
from . import indicators as ind

_LABELS = {1: "LONG", -1: "SHORT", 0: "FLAT"}

# --------------------------------------------------------------------------- #
# Portefeuille multi-actif : chaque instrument avec SA stratégie (le régime dicte
# la famille — momentum pour l'or, mean-reversion pour les indices). Voir SAVEPOINT.
# --------------------------------------------------------------------------- #
INSTRUMENTS: list[dict] = [
    {
        "ticker": "GC=F", "strategy": "ichimoku", "interval": "5m",
        "k_stop": 2.0, "k_target": 3.0,
        "note": "or · momentum Ichimoku · edge 🟡 retenu (GC seul)",
    },
    {
        "ticker": "NQ=F", "strategy": "rsi_meanrev", "interval": "5m",
        "k_stop": 2.0, "k_target": 2.0,
        "note": "nasdaq · mean-reversion RSI 25/75 · DÉMO 🟡 (edge non confirmé multi-régime)",
    },
]


@dataclass
class LiveSignal:
    ticker: str
    timestamp: pd.Timestamp
    price: float
    direction: int                 # 1 long, -1 short, 0 flat
    fresh: bool                    # la direction vient de changer sur la dernière barre
    atr: float
    k_stop: float
    k_target: float
    context: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return _LABELS[self.direction]

    @property
    def stop_price(self) -> float | None:
        if self.direction == 0 or self.atr <= 0:
            return None
        return self.price - self.direction * self.k_stop * self.atr

    @property
    def target_price(self) -> float | None:
        if self.direction == 0 or self.atr <= 0:
            return None
        return self.price + self.direction * self.k_target * self.atr

    def summary(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M")
        if self.fresh:
            etat = "  ⚡ SIGNAL FRAIS — entrer maintenant"
        elif self.direction != 0:
            etat = "  (position en cours — pas de nouveau signal)"
        else:
            etat = ""
        lines = [f"[{ts}] {self.ticker.upper()}  prix {self.price:.2f}  |  {self.label}{etat}"]
        if self.context:
            lines.append("  " + "  ·  ".join(f"{k} {v:.2f}" for k, v in self.context.items()))
        if self.direction == 0:
            lines.append("  Pas de position — attendre un signal frais.")
        elif self.fresh:
            sens = "sous" if self.direction == 1 else "au-dessus"
            lines.append(
                f"  ATR {self.atr:.2f}  ->  stop {self.stop_price:.2f} "
                f"({self.k_stop:g} ATR {sens})  ·  target {self.target_price:.2f} "
                f"({self.k_target:g} ATR)"
            )
        else:
            # Position déjà ouverte : les niveaux « au prix actuel » ne sont qu'indicatifs.
            lines.append(
                f"  ATR {self.atr:.2f}  ·  garde le stop/target de TON entrée réelle "
                f"(ces niveaux ne valent que pour une entrée au prix actuel)."
            )
        return "\n".join(lines)


def from_df(
    ticker: str,
    df: pd.DataFrame,
    strategy_name: str = "ichimoku",
    k_stop: float = 2.0,
    k_target: float = 3.0,
    atr_window: int = 14,
) -> LiveSignal:
    """Cœur pur : calcule le signal courant à partir d'un DataFrame OHLCV déjà chargé."""
    strat = backtest.STRATEGIES.get(strategy_name)
    if strat is None:
        raise ValueError(f"Stratégie inconnue : {strategy_name}")
    if df.empty:
        raise ValueError("DataFrame vide.")

    pos = strat(df).reindex(df.index).fillna(0.0)
    direction = int(pos.iloc[-1])
    prev = int(pos.iloc[-2]) if len(pos) >= 2 else 0
    fresh = direction != 0 and direction != prev

    atr = float(ind.atr(df, atr_window).iloc[-1])
    price = float(df["Close"].iloc[-1])

    context: dict = {}
    if strategy_name == "ichimoku":
        k = ind.ichimoku(df, 20, 60, 120)
        context = {
            "Tenkan": float(k["tenkan"].iloc[-1]),
            "Kijun": float(k["kijun"].iloc[-1]),
            "nuage↑": float(k[["span_a", "span_b"]].max(axis=1).iloc[-1]),
            "nuage↓": float(k[["span_a", "span_b"]].min(axis=1).iloc[-1]),
        }
    elif strategy_name == "rsi_meanrev":
        context = {"RSI": float(ind.rsi(df["Close"], 14).iloc[-1])}

    return LiveSignal(ticker, df.index[-1], price, direction, fresh, atr,
                      k_stop, k_target, context)


def compute(
    ticker: str,
    strategy_name: str = "ichimoku",
    interval: str = "5m",
    period: str = "5d",
    k_stop: float = 2.0,
    k_target: float = 3.0,
) -> LiveSignal:
    """Récupère les dernières données (sans cache, pour rester frais) et calcule le signal."""
    df = data.get_history(ticker, period=period, interval=interval, use_cache=False)
    return from_df(ticker, df, strategy_name, k_stop, k_target)
