"""Moteur de backtest vectorisé simple.

Une stratégie est une fonction ``signal(df) -> pd.Series`` renvoyant une position
cible pour chaque barre : 1.0 (long), 0.0 (cash) ou -1.0 (short). Le moteur applique
la position à la barre *suivante* (pas de look-ahead) et calcule la courbe d'equity
ainsi que quelques métriques de performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from . import indicators as ind

# Une stratégie : reçoit le DataFrame OHLCV, renvoie une série de positions cibles.
Strategy = Callable[[pd.DataFrame], pd.Series]


@dataclass
class BacktestResult:
    equity: pd.Series          # courbe d'equity (base 1.0)
    positions: pd.Series       # position appliquée à chaque barre
    returns: pd.Series         # rendements de la stratégie
    metrics: dict              # métriques agrégées

    def summary(self) -> str:
        m = self.metrics
        return (
            f"Rendement total : {m['total_return']:+.2%}\n"
            f"CAGR            : {m['cagr']:+.2%}\n"
            f"Volatilité      : {m['volatility']:.2%}\n"
            f"Sharpe          : {m['sharpe']:.2f}\n"
            f"Max drawdown    : {m['max_drawdown']:.2%}\n"
            f"Win rate        : {m['win_rate']:.2%}\n"
            f"Nb trades       : {m['n_trades']}"
        )


def _metrics(strat_ret: pd.Series, equity: pd.Series, positions: pd.Series,
             periods_per_year: int = 252) -> dict:
    clean = strat_ret.dropna()
    total_return = float(equity.iloc[-1] - 1.0) if len(equity) else 0.0
    n = len(clean)
    years = n / periods_per_year if periods_per_year else 0
    cagr = (equity.iloc[-1] ** (1 / years) - 1) if years > 0 and equity.iloc[-1] > 0 else 0.0
    vol = float(clean.std() * np.sqrt(periods_per_year)) if n > 1 else 0.0
    mean_ann = float(clean.mean() * periods_per_year)
    sharpe = mean_ann / vol if vol else 0.0

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0

    wins = (clean > 0).sum()
    win_rate = float(wins / n) if n else 0.0
    # Un "trade" = un changement de position.
    n_trades = int((positions.diff().fillna(positions) != 0).sum())

    return {
        "total_return": total_return,
        "cagr": float(cagr),
        "volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "n_trades": n_trades,
    }


def run(
    df: pd.DataFrame,
    strategy: Strategy,
    fee: float = 0.0005,
    periods_per_year: int = 252,
) -> BacktestResult:
    """Exécute ``strategy`` sur ``df`` et renvoie un :class:`BacktestResult`.

    Parameters
    ----------
    df: DataFrame OHLCV.
    strategy: fonction renvoyant les positions cibles.
    fee: coût par changement de position (fraction, ex. 0.0005 = 5 bps).
    """
    target = strategy(df).reindex(df.index).fillna(0.0)
    # On applique la position décidée à la barre t à la barre t+1 (pas de look-ahead).
    position = target.shift(1).fillna(0.0)

    asset_ret = df["Close"].pct_change().fillna(0.0)
    # Coût de transaction proportionnel au changement de position.
    turnover = position.diff().abs().fillna(position.abs())
    strat_ret = position * asset_ret - turnover * fee

    equity = (1.0 + strat_ret).cumprod()
    metrics = _metrics(strat_ret, equity, position, periods_per_year)
    return BacktestResult(equity=equity, positions=position, returns=strat_ret, metrics=metrics)


# --------------------------------------------------------------------------- #
# Stratégies d'exemple
# --------------------------------------------------------------------------- #

def sma_crossover(fast: int = 20, slow: int = 50) -> Strategy:
    """Long quand la SMA rapide passe au-dessus de la SMA lente."""
    def strat(df: pd.DataFrame) -> pd.Series:
        f = ind.sma(df["Close"], fast)
        s = ind.sma(df["Close"], slow)
        return (f > s).astype(float)
    return strat


def rsi_reversion(window: int = 14, low: float = 30, high: float = 70) -> Strategy:
    """Long en survente (RSI < low), sort en surachat (RSI > high)."""
    def strat(df: pd.DataFrame) -> pd.Series:
        r = ind.rsi(df["Close"], window)
        pos = pd.Series(np.nan, index=df.index)
        pos[r < low] = 1.0
        pos[r > high] = 0.0
        return pos.ffill().fillna(0.0)
    return strat


def macd_cross() -> Strategy:
    """Long quand la ligne MACD passe au-dessus de sa ligne de signal."""
    def strat(df: pd.DataFrame) -> pd.Series:
        m = ind.macd(df["Close"])
        return (m["macd"] > m["signal"]).astype(float)
    return strat


def bollinger_breakout(window: int = 20, n_std: float = 2.0) -> Strategy:
    """Long en cassure de la bande haute, sort sous la bande médiane."""
    def strat(df: pd.DataFrame) -> pd.Series:
        b = ind.bollinger(df["Close"], window, n_std)
        pos = pd.Series(np.nan, index=df.index)
        pos[df["Close"] > b["upper"]] = 1.0
        pos[df["Close"] < b["mid"]] = 0.0
        return pos.ffill().fillna(0.0)
    return strat


def donchian_breakout(window: int = 20) -> Strategy:
    """Cassure de canal de Donchian : long sur nouveau plus-haut ``window``."""
    def strat(df: pd.DataFrame) -> pd.Series:
        d = ind.donchian(df, window)
        pos = pd.Series(np.nan, index=df.index)
        pos[df["Close"] >= d["upper"].shift(1)] = 1.0
        pos[df["Close"] <= d["lower"].shift(1)] = 0.0
        return pos.ffill().fillna(0.0)
    return strat


def trend_adx(window: int = 14, threshold: float = 25.0) -> Strategy:
    """Suit la tendance (+DI vs -DI) uniquement quand l'ADX confirme sa force."""
    def strat(df: pd.DataFrame) -> pd.Series:
        a = ind.adx(df, window)
        strong = a["adx"] > threshold
        return ((a["plus_di"] > a["minus_di"]) & strong).astype(float)
    return strat


def buy_and_hold() -> Strategy:
    """Référence : toujours investi."""
    def strat(df: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=df.index)
    return strat


STRATEGIES: dict[str, Strategy] = {
    "sma": sma_crossover(),
    "rsi": rsi_reversion(),
    "macd": macd_cross(),
    "bollinger": bollinger_breakout(),
    "donchian": donchian_breakout(),
    "adx": trend_adx(),
    "hold": buy_and_hold(),
}
