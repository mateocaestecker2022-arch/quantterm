"""Indicateurs techniques classiques.

Les indicateurs « prix » prennent une ``pd.Series`` (généralement les cours de
clôture). Les indicateurs qui ont besoin de plusieurs colonnes (High/Low/Volume)
prennent le DataFrame OHLCV complet. Tous renvoient des objets alignés sur l'index
d'entrée.
"""

from __future__ import annotations

import numpy as np
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
        return np.log(series / series.shift(1))
    return series.pct_change()


def volatility(series: pd.Series, window: int = 20, annualize: int = 252) -> pd.Series:
    """Volatilité glissante annualisée des rendements."""
    r = returns(series)
    return r.rolling(window).std() * (annualize ** 0.5)


def wma(series: pd.Series, window: int = 20) -> pd.Series:
    """Moyenne mobile pondérée linéairement (les valeurs récentes pèsent plus)."""
    weights = np.arange(1, window + 1)
    return series.rolling(window).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


def roc(series: pd.Series, window: int = 12) -> pd.Series:
    """Rate of Change : variation en % sur ``window`` périodes."""
    return series.pct_change(window) * 100


def momentum(series: pd.Series, window: int = 10) -> pd.Series:
    """Momentum brut : différence de prix sur ``window`` périodes."""
    return series.diff(window)


def zscore(series: pd.Series, window: int = 20) -> pd.Series:
    """Z-score glissant : écart à la moyenne en nombre d'écarts-types."""
    mean = series.rolling(window).mean()
    std = series.rolling(window).std()
    return (series - mean) / std.replace(0.0, np.nan)


# --------------------------------------------------------------------------- #
# Indicateurs nécessitant High / Low / Close (prennent le DataFrame OHLCV)
# --------------------------------------------------------------------------- #

def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range : plus grande amplitude entre high-low et gaps de clôture."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range : mesure de volatilité de Wilder."""
    return true_range(df).ewm(alpha=1 / window, adjust=False).mean()


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> pd.DataFrame:
    """Oscillateur stochastique %K / %D (0-100)."""
    low_k = df["Low"].rolling(k).min()
    high_k = df["High"].rolling(k).max()
    percent_k = 100 * (df["Close"] - low_k) / (high_k - low_k).replace(0.0, np.nan)
    percent_d = percent_k.rolling(d).mean()
    return pd.DataFrame({"k": percent_k, "d": percent_d})


def williams_r(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Williams %R : oscillateur borné entre -100 (survente) et 0 (surachat)."""
    high = df["High"].rolling(window).max()
    low = df["Low"].rolling(window).min()
    return -100 * (high - df["Close"]) / (high - low).replace(0.0, np.nan)


def cci(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Commodity Channel Index : écart du prix typique à sa moyenne."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    ma = tp.rolling(window).mean()
    mad = tp.rolling(window).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - ma) / (0.015 * mad.replace(0.0, np.nan))


def adx(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Average Directional Index (+DI, -DI, ADX) : force de la tendance."""
    up = df["High"].diff()
    down = -df["Low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(df)
    atr_ = tr.ewm(alpha=1 / window, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / window, adjust=False
    ).mean() / atr_.replace(0.0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / window, adjust=False
    ).mean() / atr_.replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx_ = dx.ewm(alpha=1 / window, adjust=False).mean()
    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx_})


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume : volume cumulé signé par le sens de la clôture."""
    direction = np.sign(df["Close"].diff().fillna(0.0))
    return (direction * df["Volume"]).cumsum()


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume Weighted Average Price (cumulé sur la période fournie)."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).cumsum() / df["Volume"].cumsum().replace(0.0, np.nan)


def mfi(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Money Flow Index : RSI pondéré par le volume (0-100)."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    mf = tp * df["Volume"]
    delta = tp.diff()
    pos = mf.where(delta > 0, 0.0).rolling(window).sum()
    neg = mf.where(delta < 0, 0.0).rolling(window).sum()
    ratio = pos / neg.replace(0.0, np.nan)
    return (100 - 100 / (1 + ratio)).fillna(100.0)


def keltner(df: pd.DataFrame, window: int = 20, mult: float = 2.0) -> pd.DataFrame:
    """Canaux de Keltner : EMA centrale ± multiple de l'ATR."""
    mid = ema(df["Close"], window)
    band = mult * atr(df, window)
    return pd.DataFrame({"mid": mid, "upper": mid + band, "lower": mid - band})


def donchian(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Canaux de Donchian : plus haut / plus bas glissants et médiane."""
    upper = df["High"].rolling(window).max()
    lower = df["Low"].rolling(window).min()
    return pd.DataFrame({"upper": upper, "lower": lower, "mid": (upper + lower) / 2})
