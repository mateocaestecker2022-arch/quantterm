"""Screener : scanne un univers de tickers et calcule des métriques quant.

Pour chaque symbole on récupère l'historique et on calcule un jeu de métriques
(performance, momentum, volatilité, RSI, distance aux moyennes mobiles), le tout
renvoyé sous forme d'un DataFrame triable/filtrable.
"""

from __future__ import annotations

import pandas as pd

from . import data, indicators as ind

# Univers par défaut : quelques grandes valeurs + indices/crypto en exemple.
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "SPY", "QQQ", "BTC-USD", "ETH-USD",
]


def _metrics_for(df: pd.DataFrame) -> dict:
    close = df["Close"]
    last = float(close.iloc[-1])

    def perf(days: int) -> float:
        if len(close) <= days:
            return float("nan")
        return float(close.iloc[-1] / close.iloc[-1 - days] - 1.0)

    rsi_val = float(ind.rsi(close).iloc[-1])
    vol = float(ind.volatility(close).iloc[-1])
    sma50 = ind.sma(close, 50).iloc[-1]
    sma200 = ind.sma(close, 200).iloc[-1]
    dist_sma50 = float(last / sma50 - 1.0) if pd.notna(sma50) else float("nan")

    # Tendance : référence sur la SMA200 si disponible, sinon repli sur la SMA50.
    ref = sma200 if pd.notna(sma200) else sma50
    if pd.isna(ref):
        trend = "n/a"
    else:
        trend = "haussier" if last > ref else "baissier"

    return {
        "price": last,
        "perf_1w": perf(5),
        "perf_1m": perf(21),
        "perf_3m": perf(63),
        "rsi": rsi_val,
        "vol_ann": vol,
        "dist_sma50": dist_sma50,
        "trend": trend,
    }


def scan(
    universe: list[str] | None = None,
    period: str = "1y",
) -> pd.DataFrame:
    """Retourne un DataFrame (index = ticker) des métriques pour chaque symbole.

    Les tickers en erreur (pas de données) sont ignorés silencieusement.
    """
    universe = universe or DEFAULT_UNIVERSE
    rows: dict[str, dict] = {}
    for ticker in universe:
        try:
            df = data.get_history(ticker, period=period, interval="1d")
            if len(df) < 20:
                continue
            rows[ticker.upper()] = _metrics_for(df)
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame.from_dict(rows, orient="index")


def filter_screen(
    df: pd.DataFrame,
    *,
    rsi_max: float | None = None,
    rsi_min: float | None = None,
    trend: str | None = None,
    min_perf_1m: float | None = None,
    sort_by: str = "perf_1m",
    ascending: bool = False,
) -> pd.DataFrame:
    """Applique des filtres simples sur le résultat de :func:`scan`."""
    out = df.copy()
    if rsi_max is not None:
        out = out[out["rsi"] <= rsi_max]
    if rsi_min is not None:
        out = out[out["rsi"] >= rsi_min]
    if trend is not None:
        out = out[out["trend"] == trend]
    if min_perf_1m is not None:
        out = out[out["perf_1m"] >= min_perf_1m]
    if sort_by in out.columns:
        out = out.sort_values(sort_by, ascending=ascending)
    return out
