"""Rendu de graphiques ASCII dans le terminal via plotext.

Chaque fonction construit un graphique plotext et le renvoie sous forme de chaîne
(via ``plt.build()``) pour être affiché dans un widget Textual ``Static``.
"""

from __future__ import annotations

import pandas as pd
import plotext as plt

from . import indicators as ind


def _dates(index: pd.DatetimeIndex) -> list[str]:
    return [d.strftime("%d/%m/%Y") for d in index]


def price_chart(
    df: pd.DataFrame,
    ticker: str,
    width: int = 100,
    height: int = 30,
    overlays: tuple[int, ...] = (20, 50),
) -> str:
    """Graphique en chandeliers avec moyennes mobiles en overlay."""
    plt.clf()
    plt.plotsize(width, height)
    plt.date_form("d/m/Y")

    dates = _dates(df.index)
    data = {
        "Open": df["Open"].tolist(),
        "Close": df["Close"].tolist(),
        "High": df["High"].tolist(),
        "Low": df["Low"].tolist(),
    }
    plt.candlestick(dates, data)

    for w in overlays:
        if len(df) > w:
            plt.plot(dates, ind.sma(df["Close"], w).tolist(), label=f"SMA{w}")

    plt.title(f"{ticker} — {df.index[0].date()} → {df.index[-1].date()}")
    plt.theme("dark")
    return plt.build()


def line_chart(
    series: pd.Series,
    title: str,
    width: int = 100,
    height: int = 20,
    hline: float | None = None,
) -> str:
    """Graphique en ligne simple (equity, RSI, indicateur...)."""
    plt.clf()
    plt.plotsize(width, height)
    plt.date_form("d/m/Y")
    dates = _dates(series.index)
    plt.plot(dates, series.ffill().fillna(0).tolist())
    if hline is not None:
        plt.horizontal_line(hline)
    plt.title(title)
    plt.theme("dark")
    return plt.build()


# Oscillateurs disponibles dans le panneau bas du graphique : chaque entrée
# décrit comment extraire la ou les séries et quelles lignes de repère tracer.
OSCILLATORS = ("rsi", "macd", "stochastic", "atr", "cci", "mfi", "williams", "adx")


def oscillator_chart(
    df: pd.DataFrame,
    name: str,
    width: int = 100,
    height: int = 16,
) -> str:
    """Trace un oscillateur (RSI, MACD, stochastique, ATR...) sous le prix."""
    plt.clf()
    plt.plotsize(width, height)
    plt.date_form("d/m/Y")
    dates = _dates(df.index)
    close = df["Close"]

    def line(series, label=None):
        plt.plot(dates, series.ffill().fillna(0).tolist(), label=label)

    hlines: list[float] = []
    if name == "rsi":
        line(ind.rsi(close)); hlines = [30, 70]
        title = "RSI (14)"
    elif name == "macd":
        m = ind.macd(close)
        line(m["macd"], "MACD"); line(m["signal"], "Signal"); hlines = [0]
        title = "MACD (12,26,9)"
    elif name == "stochastic":
        s = ind.stochastic(df)
        line(s["k"], "%K"); line(s["d"], "%D"); hlines = [20, 80]
        title = "Stochastique (14,3)"
    elif name == "atr":
        line(ind.atr(df))
        title = "ATR (14)"
    elif name == "cci":
        line(ind.cci(df)); hlines = [-100, 100]
        title = "CCI (20)"
    elif name == "mfi":
        line(ind.mfi(df)); hlines = [20, 80]
        title = "Money Flow Index (14)"
    elif name == "williams":
        line(ind.williams_r(df)); hlines = [-20, -80]
        title = "Williams %R (14)"
    elif name == "adx":
        a = ind.adx(df)
        line(a["adx"], "ADX"); line(a["plus_di"], "+DI"); line(a["minus_di"], "-DI")
        hlines = [25]
        title = f"ADX / DMI (14)"
    else:
        line(ind.rsi(close)); hlines = [30, 70]
        title = "RSI (14)"

    for h in hlines:
        plt.horizontal_line(h)
    plt.title(title)
    plt.theme("dark")
    return plt.build()
