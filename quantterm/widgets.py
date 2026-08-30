"""Widgets graphiques basés sur ``textual-plotext``.

Contrairement à un ``Static`` rempli de texte plotext de taille fixe (qui déborde
dès que la fenêtre change de taille), ``PlotextPlot`` redessine le graphique à la
taille exacte du widget à chaque rendu et se redimensionne tout seul.

Chaque widget expose une méthode ``show(...)`` : on redessine sur ``self.plt`` puis
on appelle ``refresh()``.
"""

from __future__ import annotations

import pandas as pd
from textual_plotext import PlotextPlot

from . import indicators as ind

# Oscillateurs proposés dans le sélecteur de l'interface.
OSCILLATORS = ("rsi", "macd", "stochastic", "atr", "cci", "mfi", "williams", "adx")


def _dates(index: pd.DatetimeIndex) -> list[str]:
    return [d.strftime("%d/%m/%Y") for d in index]


class _BasePlot(PlotextPlot):
    """Base commune : thème sombre forcé et repère de date."""

    def on_mount(self) -> None:
        super().on_mount()
        self.theme = "dark"

    def _fresh(self):
        plt = self.plt
        plt.clear_figure()
        plt.date_form("d/m/Y")
        return plt


class PriceChart(_BasePlot):
    """Courbe de prix (clôture) + moyennes mobiles en overlay."""

    def show(self, df: pd.DataFrame, ticker: str, overlays: tuple[int, ...] = (20, 50)) -> None:
        plt = self._fresh()
        dates = _dates(df.index)
        plt.plot(dates, df["Close"].tolist(), label="Clôture")
        for w in overlays:
            if len(df) > w:
                plt.plot(dates, ind.sma(df["Close"], w).tolist(), label=f"SMA{w}")
        plt.title(f"{ticker}  ({df.index[0].date()} → {df.index[-1].date()})")
        self.refresh()


class EquityChart(_BasePlot):
    """Courbe d'equity (base 1.0) d'un backtest."""

    def show(self, equity: pd.Series, title: str) -> None:
        plt = self._fresh()
        dates = _dates(equity.index)
        plt.plot(dates, equity.ffill().fillna(1.0).tolist())
        plt.horizontal_line(1.0)
        plt.title(title)
        self.refresh()


class OscillatorChart(_BasePlot):
    """Oscillateur configurable (RSI, MACD, stochastique, ATR...)."""

    def show(self, df: pd.DataFrame, name: str) -> None:
        plt = self._fresh()
        dates = _dates(df.index)
        close = df["Close"]

        def line(series, label=None):
            plt.plot(dates, series.ffill().fillna(0).tolist(), label=label)

        hlines: list[float] = []
        if name == "macd":
            m = ind.macd(close)
            line(m["macd"], "MACD"); line(m["signal"], "Signal"); hlines = [0]
            title = "MACD (12,26,9)"
        elif name == "stochastic":
            s = ind.stochastic(df)
            line(s["k"], "%K"); line(s["d"], "%D"); hlines = [20, 80]
            title = "Stochastique (14,3)"
        elif name == "atr":
            line(ind.atr(df)); title = "ATR (14)"
        elif name == "cci":
            line(ind.cci(df)); hlines = [-100, 100]; title = "CCI (20)"
        elif name == "mfi":
            line(ind.mfi(df)); hlines = [20, 80]; title = "Money Flow Index (14)"
        elif name == "williams":
            line(ind.williams_r(df)); hlines = [-20, -80]; title = "Williams %R (14)"
        elif name == "adx":
            a = ind.adx(df)
            line(a["adx"], "ADX"); line(a["plus_di"], "+DI"); line(a["minus_di"], "-DI")
            hlines = [25]; title = "ADX / DMI (14)"
        else:  # rsi par défaut
            line(ind.rsi(close)); hlines = [30, 70]; title = "RSI (14)"

        for h in hlines:
            plt.horizontal_line(h)
        plt.title(title)
        self.refresh()
