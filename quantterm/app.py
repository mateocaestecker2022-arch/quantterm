"""Application TUI (Textual) du terminal quant — disposition « Bloomberg ».

Interface dense, tout visible en même temps :
- barre de contrôles en haut (ticker, période, stratégie, oscillateur) ;
- colonne gauche : graphique de prix + oscillateur + courbe d'equity ;
- colonne droite : cotation, watchlist/screener cliquable, métriques de backtest.

Les graphiques utilisent des widgets ``textual-plotext`` qui se redimensionnent
automatiquement. Les appels réseau (yfinance) tournent dans des threads.
"""

from __future__ import annotations

import asyncio

import pandas as pd
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from . import backtest, data, propfirm, screener
from .widgets import OSCILLATORS, EquityChart, OscillatorChart, PriceChart

PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]

# Palette « terminal financier » : fond noir, accents ambre, vert/rouge directionnels.
AMBER = "#ffb000"
GREEN = "#00d75f"
RED = "#ff3b3b"
DIM = "#7a7a7a"


def _color(x: float) -> str:
    return GREEN if x >= 0 else RED


class QuantTerminal(App):
    """Terminal quant dense, style Bloomberg."""

    CSS = f"""
    Screen {{ background: #000000; }}

    #controls {{
        height: 3;
        background: #0d0d0d;
        border-bottom: heavy {AMBER};
        padding: 0 1;
        align-vertical: middle;
    }}
    #controls Input {{ width: 22; border: tall {AMBER}; background: #000; }}
    #controls Select {{ width: 16; }}
    #controls Label {{ color: {AMBER}; text-style: bold; padding: 0 1; }}

    #body {{ height: 1fr; }}

    #left {{ width: 3fr; }}
    #right {{ width: 52; border-left: heavy {AMBER}; padding: 0 1; }}

    #price_chart {{ height: 24; border: round {DIM}; }}
    #osc_chart {{ height: 15; border: round {DIM}; }}
    #equity_chart {{ height: 17; border: round {DIM}; }}

    .panel {{ border: round {DIM}; padding: 0 1; margin: 0 0 1 0; }}
    .panel-title {{ color: {AMBER}; text-style: bold; }}

    #quote {{ height: 5; content-align: left middle; }}
    #metrics {{ color: {GREEN}; height: auto; }}
    #prop {{ height: auto; }}
    #screen_table {{ height: 1fr; }}

    DataTable {{ background: #000; }}
    DataTable > .datatable--header {{ background: #0d0d0d; color: {AMBER}; text-style: bold; }}
    DataTable > .datatable--cursor {{ background: {AMBER}; color: #000; }}

    Header {{ background: #0d0d0d; color: {AMBER}; }}
    Footer {{ background: #0d0d0d; }}
    """

    BINDINGS = [
        ("q", "quit", "Quitter"),
        ("r", "refresh", "Rafraîchir"),
        ("f", "focus_ticker", "Ticker"),
        ("s", "rescan", "Re-scan"),
    ]

    TITLE = "QUANTTERM"
    SUB_TITLE = "terminal quant"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="controls"):
            yield Label("TICKER")
            yield Input(value="AAPL", placeholder="AAPL, BTC-USD…", id="ticker")
            yield Label("PÉRIODE")
            yield Select([(p, p) for p in PERIODS], value="1y", id="period", allow_blank=False)
            yield Label("STRATÉGIE")
            yield Select([(k, k) for k in backtest.STRATEGIES], value="sma",
                         id="strategy", allow_blank=False)
            yield Label("OSCILL.")
            yield Select([(o, o) for o in OSCILLATORS], value="rsi",
                         id="oscillator", allow_blank=False)
            yield Label("PROP")
            yield Select([(k, k) for k in propfirm.PRESETS], value="2step-p1",
                         id="preset", allow_blank=False)
        with Horizontal(id="body"):
            with VerticalScroll(id="left"):
                yield PriceChart(id="price_chart")
                yield OscillatorChart(id="osc_chart")
                yield EquityChart(id="equity_chart")
            with Vertical(id="right"):
                yield Static("Chargement…", classes="panel", id="quote")
                yield Label("● WATCHLIST", classes="panel-title")
                yield DataTable(id="screen_table")
                yield Label("● BACKTEST", classes="panel-title")
                yield Static("", classes="panel", id="metrics")
                yield Label("● PROP FIRM", classes="panel-title")
                yield Static("—", classes="panel", id="prop")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#screen_table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
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

    @on(Select.Changed, "#preset")
    def _on_preset(self) -> None:
        self.load_backtest()

    @on(DataTable.RowSelected, "#screen_table")
    def _on_row(self, event: DataTable.RowSelected) -> None:
        # Un clic sur la watchlist charge le ticker correspondant.
        ticker = str(event.row_key.value) if event.row_key else None
        if ticker:
            self.query_one("#ticker", Input).value = ticker
            self.load_ticker()

    def action_refresh(self) -> None:
        self.load_ticker()

    def action_rescan(self) -> None:
        self.load_screener()

    def action_focus_ticker(self) -> None:
        self.query_one("#ticker", Input).focus()

    # ---- helpers -------------------------------------------------------- #

    def _ticker(self) -> str:
        return self.query_one("#ticker", Input).value.strip().upper() or "AAPL"

    def _period(self) -> str:
        return self.query_one("#period", Select).value

    def _strategy(self) -> str:
        return self.query_one("#strategy", Select).value

    def _oscillator(self) -> str:
        return self.query_one("#oscillator", Select).value

    def _preset(self) -> str:
        return self.query_one("#preset", Select).value

    def render_oscillator(self) -> None:
        df = getattr(self, "_df", None)
        if df is None or df.empty:
            return
        self.query_one("#osc_chart", OscillatorChart).show(df, self._oscillator())

    def _render_quote(self, ticker: str, df: pd.DataFrame) -> None:
        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2]) if len(df) >= 2 else last
        chg = last - prev
        pct = (chg / prev * 100) if prev else 0.0
        c = _color(chg)
        arrow = "▲" if chg >= 0 else "▼"
        hi = float(df["High"].iloc[-1])
        lo = float(df["Low"].iloc[-1])
        vol = float(df["Volume"].iloc[-1])
        self.query_one("#quote", Static).update(
            f"[b {AMBER}]{ticker}[/]\n"
            f"[b {c}]{last:,.2f}[/]  [{c}]{arrow} {chg:+.2f} ({pct:+.2f}%)[/]\n"
            f"[{DIM}]H[/] {hi:,.2f}  [{DIM}]L[/] {lo:,.2f}  [{DIM}]Vol[/] {vol:,.0f}"
        )

    # ---- chargement ----------------------------------------------------- #

    @work(exclusive=True, group="ticker")
    async def load_ticker(self) -> None:
        ticker, period = self._ticker(), self._period()
        quote = self.query_one("#quote", Static)
        quote.update(f"[{AMBER}]Chargement de {ticker}…[/]")
        try:
            df = await asyncio.to_thread(data.get_history, ticker, period)
        except Exception as exc:  # noqa: BLE001
            quote.update(f"[{RED}]Erreur : {exc}[/]")
            return
        self._df = df
        self.query_one("#price_chart", PriceChart).show(df, ticker)
        self._render_quote(ticker, df)
        self.render_oscillator()
        self.load_backtest()

    @work(exclusive=True, group="backtest")
    async def load_backtest(self) -> None:
        df = getattr(self, "_df", None)
        if df is None or df.empty:
            return
        name = self._strategy()
        result = await asyncio.to_thread(backtest.run, df, backtest.STRATEGIES[name])
        self.query_one("#equity_chart", EquityChart).show(
            result.equity, f"Equity — '{name}' (base 1.0)"
        )
        self.query_one("#metrics", Static).update(_metrics_markup(result.metrics))

        rules = propfirm.PRESETS[self._preset()]
        verdict = propfirm.evaluate(result.equity, rules, positions=result.positions)
        self.query_one("#prop", Static).update(_prop_markup(verdict))

    @work(exclusive=True, group="screener")
    async def load_screener(self) -> None:
        table = self.query_one("#screen_table", DataTable)
        df = await asyncio.to_thread(screener.scan)
        table.clear(columns=True)
        if df.empty:
            return
        df = screener.filter_screen(df, sort_by="perf_1m")
        table.add_column("SYM", key="sym")
        table.add_column("PRIX")
        table.add_column("1M")
        table.add_column("RSI")
        for ticker, row in df.iterrows():
            table.add_row(
                Text(str(ticker), style=f"bold {AMBER}"),
                Text(f"{row['price']:,.2f}"),
                _pct_cell(row["perf_1m"]),
                _rsi_cell(row["rsi"]),
                key=str(ticker),
            )


# --------------------------------------------------------------------------- #
# Rendu (helpers de formatage colorés)
# --------------------------------------------------------------------------- #

def _pct_cell(x) -> Text:
    if pd.isna(x):
        return Text("n/a", style=DIM)
    return Text(f"{x:+.1%}", style=_color(x))


def _rsi_cell(x) -> Text:
    if pd.isna(x):
        return Text("n/a", style=DIM)
    style = RED if x > 70 else GREEN if x < 30 else "white"
    return Text(f"{x:.0f}", style=style)


def _metrics_markup(m: dict) -> str:
    def line(label: str, value: str, val_color: str = "white") -> str:
        return f"[{DIM}]{label:<14}[/] [{val_color}]{value}[/]"

    return "\n".join([
        line("Rendement", f"{m['total_return']:+.2%}", _color(m["total_return"])),
        line("CAGR", f"{m['cagr']:+.2%}", _color(m["cagr"])),
        line("Volatilité", f"{m['volatility']:.2%}"),
        line("Sharpe", f"{m['sharpe']:.2f}", _color(m["sharpe"])),
        line("Max drawdown", f"{m['max_drawdown']:.2%}", RED),
        line("Win rate", f"{m['win_rate']:.2%}"),
        line("Nb trades", f"{m['n_trades']}"),
    ])


def _prop_markup(v: "propfirm.PropFirmResult") -> str:
    badge = f"[b {GREEN}]✓ RÉUSSI[/]" if v.passed else f"[b {RED}]✗ ÉCHOUÉ[/]"
    dd_c = GREEN if v.max_drawdown > -v.rules.max_total_loss else RED
    day_c = GREEN if v.worst_daily_loss > -v.rules.max_daily_loss else RED
    return (
        f"[{AMBER}]{v.rules.name}[/]  {badge}\n"
        f"[{DIM}]{v.reason}[/]\n"
        f"[{DIM}]Pire jour[/] [{day_c}]{v.worst_daily_loss:+.2%}[/]  "
        f"[{DIM}]DD[/] [{dd_c}]{v.max_drawdown:+.2%}[/]  "
        f"[{DIM}]jours[/] {v.trading_days}"
    )


def main() -> None:
    QuantTerminal().run()


if __name__ == "__main__":
    main()
