"""Récupération des données de marché via yfinance, avec cache local sur disque.

Les données OHLCV sont téléchargées puis mises en cache au format parquet dans
``.cache/`` pour éviter de retélécharger à chaque lancement.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(".cache")
# Durée de vie du cache en secondes (par défaut 1h). Passé ce délai, on retélécharge.
CACHE_TTL = 60 * 60

# Colonnes OHLCV normalisées utilisées dans tout le projet.
OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _cache_path(ticker: str, period: str, interval: str) -> Path:
    key = f"{ticker.upper()}_{period}_{interval}".replace("/", "-")
    return CACHE_DIR / f"{key}.parquet"


def _is_fresh(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Aplatit les colonnes yfinance (parfois multi-index) en OHLCV simple."""
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance renvoie un MultiIndex (champ, ticker) pour un seul ticker aussi.
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    # Garde uniquement les colonnes connues, dans l'ordre.
    cols = [c for c in OHLCV if c in df.columns]
    df = df[cols].dropna(how="all")
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    return df


def get_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """Retourne un DataFrame OHLCV pour ``ticker``.

    Parameters
    ----------
    ticker: symbole (ex. "AAPL", "BTC-USD", "^GSPC").
    period: fenêtre historique yfinance ("1mo", "6mo", "1y", "5y", "max"...).
    interval: granularité ("1d", "1h", "1wk"...).
    use_cache: si True, sert le cache local quand il est frais.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    path = _cache_path(ticker, period, interval)

    if use_cache and _is_fresh(path):
        return pd.read_parquet(path)

    raw = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if raw is None or raw.empty:
        raise ValueError(f"Aucune donnée pour '{ticker}' (period={period}, interval={interval}).")

    df = _normalize(raw)
    try:
        df.to_parquet(path)
    except Exception:
        # Le cache est un bonus : on ignore une éventuelle erreur d'écriture.
        pass
    return df


def latest_quote(ticker: str) -> dict:
    """Retourne un instantané simple (dernier prix, variation) pour un ticker."""
    df = get_history(ticker, period="5d", interval="1d")
    if len(df) < 1:
        raise ValueError(f"Pas de cotation pour '{ticker}'.")
    last = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2]) if len(df) >= 2 else last
    change = last - prev
    pct = (change / prev * 100) if prev else 0.0
    return {"ticker": ticker.upper(), "price": last, "change": change, "pct": pct}
