"""Application TUI (Textual) du terminal quant.

Trois onglets : graphique de prix, backtest de stratégie et screener d'univers.
Les appels réseau (yfinance) sont exécutés dans des threads pour ne pas bloquer
l'interface.
"""

from __future__ import annotations

import asyncio

import pandas as pd
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from . import backtest, charts, data, screener

PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]


class QuantTerminal(App):
    """Terminal quant dans le terminal."""

    CSS = """
    #controls { height: auto; padding: 0 1; }
    #controls Input { width: 24; }
    #controls Select { width: 18; }
    .chart { padding: 1; }
    #metrics { padding: 1; color: $success; }
    DataTable { height: 1fr; }
    """

    BINDINGS = [
        ("q", "quit", "Quitter"),
        ("r", "refresh", "Rafraîchir"),
    ]

    TITLE = "QuantTerm"
    SUB_TITLE = "Terminal quant"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="controls"):
            yield Input(value="AAPL", placeholder="Ticker (ex. AAPL, BTC-USD)", id="ticker")
            yield Select(
                [(p, p) for p in PERIODS], value="1y", id="period", allow_blank=False
            )
            yield Select(
                [(k, k) for k in backtest.STRATEGIES], value="sma", id="strategy",
                allow_blank=False,
            )
            yield Select(
                [(o, o) for o in charts.OSCILLATORS], value="rsi", id="oscillator",
                allow_blank=False,
            )
        with TabbedContent(initial="tab-chart"):
            with TabPane("Graphique", id="tab-chart"):
                with VerticalScroll():
                    yield Static("Entre un ticker puis appuie sur Entrée.", classes="chart", id="price_chart")
                    yield Static("", classes="chart", id="osc_chart")
            with TabPane("Backtest", id="tab-backtest"):
                with VerticalScroll():
                    yield Static("", classes="chart", id="equity_chart")
                    yield Static("", id="metrics")
            with TabPane("Screener", id="tab-screener"):
                yield Label("Scan de l'univers par défaut (peut prendre quelques secondes)...", id="screen_status")
                yield DataTable(id="screen_table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#screen_table", DataTable)
        table.cursor_type = "row"
        self.load_ticker()
        self.load_screener()

    # ---- entrées utilisateur ------------------------------------------- #

    @on(Input.Submitted, "#ticker")
    @on(Select.Changed, "#period")
    def _on_change(self) -> None:
        self.load_ticker()

    @on(Select.Changed, "#strategy")
    def _on_strategy(self) -> None:
        self.load_backtest()

    @on(Select.Changed, "#oscillator")
    def _on_oscillator(self) -> None:
        self.render_oscillator()

    def action_refresh(self) -> None:
        self.load_ticker()
        self.load_screener()

    # ---- helpers -------------------------------------------------------- #

    def _ticker(self) -> str:
        return self.query_one("#ticker", Input).value.strip().upper() or "AAPL"

    def _period(self) -> str:
        return self.query_one("#period", Select).value

    def _strategy(self) -> str:
        return self.query_one("#strategy", Select).value

    def _oscillator(self) -> str:
        return self.query_one("#oscillator", Select).value

    def _chart_width(self) -> int:
        """Largeur de graphique adaptée à la fenêtre (évite le débordement plotext)."""
        return max(40, self.size.width - 8)

    def render_oscillator(self) -> None:
        """Redessine le panneau oscillateur à partir des données déjà chargées."""
        df = getattr(self, "_df", None)
        panel = self.query_one("#osc_chart", Static)
        if df is None or df.empty:
            return
        panel.update(
            charts.oscillator_chart(df, self._oscillator(), width=self._chart_width(), height=14)
        )

    def on_resize(self) -> None:
        """Re-rend les graphiques déjà chargés à la nouvelle taille (sans réseau)."""
        df = getattr(self, "_df", None)
        if df is None or df.empty:
            return
        self.query_one("#price_chart", Static).update(
            charts.price_chart(df, self._ticker(), width=self._chart_width(), height=24)
        )
        self.render_oscillator()
        eq = getattr(self, "_equity", None)
        if eq is not None:
            self.query_one("#equity_chart", Static).update(
                charts.line_chart(eq, f"Equity — stratégie '{self._strategy()}' (base 1.0)",
                                  width=self._chart_width(), height=18)
            )

    # ---- graphique de prix + backtest ---------------------------------- #

    @work(exclusive=True, group="ticker")
    async def load_ticker(self) -> None:
        ticker, period = self._ticker(), self._period()
        chart = self.query_one("#price_chart", Static)
        chart.update(f"Chargement de {ticker}...")
        try:
            df = await asyncio.to_thread(data.get_history, ticker, period)
        except Exception as exc:  # noqa: BLE001
            chart.update(f"[red]Erreur : {exc}[/red]")
            return
        self._df = df
        chart.update(charts.price_chart(df, ticker, width=self._chart_width(), height=24))
        self.render_oscillator()
        self.load_backtest()

    @work(exclusive=True, group="backtest")
    async def load_backtest(self) -> None:
        df = getattr(self, "_df", None)
        if df is None or df.empty:
            return
        strat = backtest.STRATEGIES[self._strategy()]
        result = await asyncio.to_thread(backtest.run, df, strat)
        self._equity = result.equity
        self.query_one("#equity_chart", Static).update(
            charts.line_chart(result.equity, f"Equity — stratégie '{self._strategy()}' (base 1.0)",
                              width=self._chart_width(), height=18)
        )
        self.query_one("#metrics", Static).update(result.summary())

    # ---- screener ------------------------------------------------------- #

    @work(exclusive=True, group="screener")
    async def load_screener(self) -> None:
        status = self.query_one("#screen_status", Label)
        table = self.query_one("#screen_table", DataTable)
        status.update("Scan en cours...")
        df = await asyncio.to_thread(screener.scan)
        table.clear(columns=True)
        if df.empty:
            status.update("[red]Aucune donnée récupérée.[/red]")
            return
        df = screener.filter_screen(df, sort_by="perf_1m")
        table.add_column("Ticker")
        table.add_columns("Prix", "Perf 1s", "Perf 1m", "Perf 3m", "RSI", "Vol.", "Tendance")
        for ticker, row in df.iterrows():
            table.add_row(
                ticker,
                f"{row['price']:.2f}",
                _pct(row["perf_1w"]),
                _pct(row["perf_1m"]),
                _pct(row["perf_3m"]),
                f"{row['rsi']:.0f}",
                _pct(row["vol_ann"]),
                str(row["trend"]),
            )
        status.update(f"{len(df)} actifs scannés — triés par performance 1 mois.")


def _pct(x) -> str:
    return "n/a" if pd.isna(x) else f"{x:+.1%}"


def main() -> None:
    QuantTerminal().run()


if __name__ == "__main__":
    main()
