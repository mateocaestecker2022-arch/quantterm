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


def ichimoku_trend(tenkan: int = 20, kijun: int = 60, senkou_b: int = 120) -> Strategy:
    """Suivi de tendance Ichimoku : long si Tenkan > Kijun **et** prix au-dessus du
    nuage ; short si Tenkan < Kijun **et** prix sous le nuage ; flat sinon (maintenu).

    Paramètres par défaut « lents » (20/60/120), adaptés aux graphiques intraday :
    edge identifié sur l'or en 5 min. Se prête à un stop/target ATR via
    :func:`run_intrabar`.
    """
    def strat(df: pd.DataFrame) -> pd.Series:
        k = ind.ichimoku(df, tenkan, kijun, senkou_b)
        top = k[["span_a", "span_b"]].max(axis=1)
        bot = k[["span_a", "span_b"]].min(axis=1)
        c = df["Close"]
        pos = pd.Series(np.nan, index=df.index)
        pos[(k["tenkan"] > k["kijun"]) & (c > top)] = 1.0
        pos[(k["tenkan"] < k["kijun"]) & (c < bot)] = -1.0
        return pos.ffill().fillna(0.0)
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
    "ichimoku": ichimoku_trend(),
    "hold": buy_and_hold(),
}


# --------------------------------------------------------------------------- #
# Backtest événementiel intra-barre (stop / target en ATR)
# --------------------------------------------------------------------------- #

@dataclass
class IntrabarResult:
    equity: pd.Series          # equity mark-to-market (base 1.0), alignée sur les barres
    trades: pd.Series          # rendement de chaque trade (indexé par barre de sortie)
    positions: pd.Series       # position détenue à chaque barre (-1/0/1)
    metrics: dict

    def summary(self) -> str:
        m = self.metrics
        return (
            f"Rendement total : {m['total_return']:+.2%}\n"
            f"Sharpe (trades) : {m['sharpe']:.2f}\n"
            f"Max drawdown    : {m['max_drawdown']:.2%}\n"
            f"Win rate        : {m['win_rate']:.2%}\n"
            f"Gain/trade      : {m['per_trade']:+.4%}\n"
            f"Nb trades       : {m['n_trades']}"
        )


def run_intrabar(
    df: pd.DataFrame,
    strategy: Strategy,
    fee: float = 0.0001,
    atr_window: int = 14,
    k_stop: float = 2.0,
    k_target: float = 3.0,
    max_hold: int = 48,
) -> IntrabarResult:
    """Exécute ``strategy`` en simulant l'exécution **intra-barre**.

    Contrairement à :func:`run` (close-to-close, position continue), ce moteur :

    - entre à l'**open de la barre suivante** sur une *transition* de signal (nouveau
      croisement), jamais sur l'état persistant → pas de ré-entrée en boucle ;
    - place un **stop** à ``k_stop`` ATR et un **target** à ``k_target`` ATR, vérifiés
      sur le High/Low de chaque barre ; si les deux sont atteignables dans la même
      barre, on suppose le **stop d'abord** (hypothèse conservatrice) ;
    - sort aussi sur *time-stop* (``max_hold`` barres) ou signal inverse frais ;
    - applique ``fee`` en coût round-trip par trade.

    ``fee`` est ici le coût **aller-retour** (défaut 1 bp), pas par côté comme dans
    :func:`run`.
    """
    target = strategy(df).reindex(df.index).fillna(0.0)
    atr = ind.atr(df, atr_window)

    o = df["Open"].to_numpy(); h = df["High"].to_numpy()
    lo = df["Low"].to_numpy(); c = df["Close"].to_numpy()
    a = atr.to_numpy()
    desired = np.sign(target.to_numpy())
    n = len(df)

    # Signal « frais » : la direction désirée change par rapport à la barre précédente.
    fresh = np.zeros(n)
    for i in range(1, n):
        if desired[i] != 0 and desired[i] != desired[i - 1]:
            fresh[i] = desired[i]

    state = 0
    entry = stop = tgt = 0.0
    held = 0
    pending = 0
    realized = 1.0                       # equity des trades clôturés
    eq_curve = np.ones(n)                # mark-to-market barre par barre
    pos_curve = np.zeros(n)
    trade_ret = []
    trade_idx = []

    for i in range(n):
        # (1) entrée programmée à l'open de cette barre
        if state == 0 and pending != 0 and not np.isnan(a[i]) and a[i] > 0:
            state = pending
            entry = o[i]
            if state == 1:
                stop, tgt = entry - k_stop * a[i], entry + k_target * a[i]
            else:
                stop, tgt = entry + k_stop * a[i], entry - k_target * a[i]
            held = 0
            pending = 0

        # (2) gestion d'une position ouverte (intra-barre)
        if state != 0:
            held += 1
            exit_price = None
            if state == 1:
                if lo[i] <= stop:
                    exit_price = stop
                elif h[i] >= tgt:
                    exit_price = tgt
            else:
                if h[i] >= stop:
                    exit_price = stop
                elif lo[i] <= tgt:
                    exit_price = tgt
            if exit_price is None and (held >= max_hold or fresh[i] == -state):
                exit_price = c[i]

            if exit_price is not None:
                r = state * (exit_price / entry - 1.0) - fee
                realized *= (1.0 + r)
                trade_ret.append(r)
                trade_idx.append(df.index[i])
                pos_curve[i] = state
                state = 0
            else:
                pos_curve[i] = state

        # equity mark-to-market : réalisé × PnL latent de la position ouverte
        unreal = state * (c[i] / entry - 1.0) if state != 0 else 0.0
        eq_curve[i] = realized * (1.0 + unreal)

        # (3) programmer une entrée pour la barre suivante sur signal frais uniquement
        if state == 0 and fresh[i] != 0:
            pending = int(fresh[i])

    equity = pd.Series(eq_curve, index=df.index)
    positions = pd.Series(pos_curve, index=df.index)
    trades = pd.Series(trade_ret, index=pd.DatetimeIndex(trade_idx)) if trade_ret \
        else pd.Series(dtype=float)
    return IntrabarResult(equity, trades, positions, _intrabar_metrics(trades, equity))


def _intrabar_metrics(trades: pd.Series, equity: pd.Series) -> dict:
    n = len(trades)
    total_return = float(equity.iloc[-1] - 1.0) if len(equity) else 0.0
    running_max = equity.cummax()
    max_dd = float((equity / running_max - 1.0).min()) if len(equity) else 0.0
    if n == 0:
        return {"total_return": total_return, "sharpe": 0.0, "max_drawdown": max_dd,
                "win_rate": 0.0, "per_trade": 0.0, "n_trades": 0}
    win_rate = float((trades > 0).mean())
    per_trade = float(trades.mean())
    # Sharpe par trade (non annualisé) : simple et robuste au nombre de barres.
    sharpe = float(trades.mean() / trades.std()) if trades.std() > 0 else 0.0
    return {"total_return": total_return, "sharpe": sharpe, "max_drawdown": max_dd,
            "win_rate": win_rate, "per_trade": per_trade, "n_trades": n}
