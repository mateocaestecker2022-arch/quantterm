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
