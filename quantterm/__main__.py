"""Point d'entrée : ``python -m quantterm``.

Sans argument : lance l'interface TUI.
Avec des sous-commandes : accès rapide en ligne de commande.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="quantterm",
        description="Terminal quant — data marché, backtesting et screener.",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_bt = sub.add_parser("backtest", help="Backtest en ligne de commande")
    p_bt.add_argument("ticker")
    p_bt.add_argument("--strategy", default="sma", help="sma | rsi | hold")
    p_bt.add_argument("--period", default="2y")

    p_sc = sub.add_parser("screen", help="Screener en ligne de commande")
    p_sc.add_argument("--period", default="1y")

    p_q = sub.add_parser("quote", help="Cotation rapide d'un ticker")
    p_q.add_argument("ticker")

    args = parser.parse_args()

    if args.cmd == "backtest":
        from . import backtest, data

        df = data.get_history(args.ticker, period=args.period)
        strat = backtest.STRATEGIES.get(args.strategy)
        if strat is None:
            sys.exit(f"Stratégie inconnue : {args.strategy}")
        result = backtest.run(df, strat)
        print(f"\nBacktest {args.ticker.upper()} — stratégie '{args.strategy}' ({args.period})\n")
        print(result.summary())
    elif args.cmd == "screen":
        from . import screener

        df = screener.scan(period=args.period)
        df = screener.filter_screen(df, sort_by="perf_1m")
        with_pct = df.copy()
        for col in ("perf_1w", "perf_1m", "perf_3m", "vol_ann", "dist_sma50"):
            with_pct[col] = (with_pct[col] * 100).round(1)
        print(with_pct.to_string())
    elif args.cmd == "quote":
        from . import data

        q = data.latest_quote(args.ticker)
        print(f"{q['ticker']} : {q['price']:.2f} ({q['change']:+.2f} / {q['pct']:+.2f}%)")
    else:
        # Pas de sous-commande → interface TUI.
        from .app import main as run_app

        run_app()


if __name__ == "__main__":
    main()
