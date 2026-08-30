"""Indicateurs techniques classiques, calculés sur des séries pandas.

Toutes les fonctions prennent une ``pd.Series`` (généralement les cours de clôture)
et retournent une ``pd.Series`` alignée sur le même index.
"""

from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, window: int = 20) -> pd.Series:
    """Moyenne mobile simple."""
    return series.rolling(window).mean()


def ema(series: pd.Series, window: int = 20) -> pd.Series:
    """Moyenne mobile exponentielle."""
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (0-100)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    return (100 - 100 / (1 + rs)).fillna(100.0)


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD, ligne de signal et histogramme."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def bollinger(series: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.DataFrame:
    """Bandes de Bollinger (moyenne, bande haute, bande basse)."""
    mid = sma(series, window)
    std = series.rolling(window).std()
    return pd.DataFrame(
        {"mid": mid, "upper": mid + n_std * std, "lower": mid - n_std * std}
    )


def returns(series: pd.Series, log: bool = False) -> pd.Series:
    """Rendements période à période (simples ou log)."""
    if log:
        import numpy as np

        return np.log(series / series.shift(1))
    return series.pct_change()


def volatility(series: pd.Series, window: int = 20, annualize: int = 252) -> pd.Series:
    """Volatilité glissante annualisée des rendements."""
    r = returns(series)
    return r.rolling(window).std() * (annualize ** 0.5)
