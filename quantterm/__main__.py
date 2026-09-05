"""Point d'entrée : ``python -m quantterm``.

Sans argument : lance l'interface TUI.
Avec des sous-commandes : accès rapide en ligne de commande.
"""

from __future__ import annotations

import argparse
import sys


def _force_utf8() -> None:
    """Console Windows en cp1252 : force la sortie en UTF-8 (accents, flèches…)."""
    for stream in (sys.stdout, sys.stderr):
        reconfig = getattr(stream, "reconfigure", None)
        if reconfig is not None:
            try:
                reconfig(encoding="utf-8")
            except (ValueError, OSError):
                pass


def main() -> None:
    _force_utf8()
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

    p_scalp = sub.add_parser("scalp", help="Backtest scalp intra-barre (stop/target ATR)")
    p_scalp.add_argument("ticker")
    p_scalp.add_argument("--strategy", default="ichimoku")
    p_scalp.add_argument("--interval", default="5m", help="granularité intraday (5m, 15m, 1h...)")
    p_scalp.add_argument("--period", default="60d")
    p_scalp.add_argument("--stop", type=float, default=2.0, help="stop en multiples d'ATR")
    p_scalp.add_argument("--target", type=float, default=3.0, help="target en multiples d'ATR")
    p_scalp.add_argument("--fee", type=float, default=1.0, help="coût aller-retour en bps")
    p_scalp.add_argument("--prop", default=None,
                         help="évalue aussi un preset prop firm (2step-p1 | 1step | ...)")
    p_scalp.add_argument("--capital", type=float, default=None,
                         help="capital du compte : dimensionne le nb de contrats (avec --prop)")
    p_scalp.add_argument("--contract", default=None,
                         help="contrat future (MGC | GC | MNQ | NQ | MES | ES | MCL | CL)")

    p_sig = sub.add_parser("signal", help="Signal live long/short/flat (démo/VPS)")
    p_sig.add_argument("ticker")
    p_sig.add_argument("--strategy", default="ichimoku")
    p_sig.add_argument("--interval", default="5m")
    p_sig.add_argument("--stop", type=float, default=2.0, help="stop en multiples d'ATR")
    p_sig.add_argument("--target", type=float, default=3.0, help="target en multiples d'ATR")
    p_sig.add_argument("--watch", type=int, default=0,
                       help="rafraîchit toutes les N secondes en boucle (0 = une seule fois)")
    p_sig.add_argument("--telegram", action="store_true",
                       help="envoie les signaux frais sur Telegram "
                            "(config via QUANTTERM_TG_TOKEN / QUANTTERM_TG_CHAT)")

    p_w = sub.add_parser("watch", help="Signal live multi-actif (portefeuille démo : or + nasdaq)")
    p_w.add_argument("--every", type=int, default=0,
                     help="rafraîchit toutes les N secondes en boucle (0 = une seule fois)")
    p_w.add_argument("--telegram", action="store_true",
                     help="envoie les signaux frais sur Telegram "
                          "(config via QUANTTERM_TG_TOKEN / QUANTTERM_TG_CHAT)")

    p_pf = sub.add_parser("prop", help="Évaluation challenge prop firm")
    p_pf.add_argument("ticker")
    p_pf.add_argument("--strategy", default="sma")
    p_pf.add_argument("--preset", default="2step-p1", help="2step-p1 | 2step-p2 | 1step | instant")
    p_pf.add_argument("--period", default="2y")
    p_pf.add_argument("--scan", action="store_true",
                      help="Cherche toutes les stratégies/presets qui valident pour ce ticker")

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
    elif args.cmd == "scalp":
        from . import backtest, data, propfirm

        df = data.get_history(args.ticker, period=args.period, interval=args.interval)
        strat = backtest.STRATEGIES.get(args.strategy)
        if strat is None:
            sys.exit(f"Stratégie inconnue : {args.strategy}")
        res = backtest.run_intrabar(
            df, strat, fee=args.fee * 1e-4, k_stop=args.stop, k_target=args.target,
        )
        print(f"\nScalp {args.ticker.upper()} — '{args.strategy}' {args.interval} "
              f"({args.period}, stop {args.stop}ATR / target {args.target}ATR, "
              f"{args.fee}bps RT)\n")
        print(res.summary())
        if args.prop:
            rules = propfirm.PRESETS.get(args.prop)
            if rules is None:
                sys.exit(f"Preset inconnu : {args.prop} (dispo : {', '.join(propfirm.PRESETS)})")
            if args.capital and args.contract:
                spec = propfirm.CONTRACTS.get(args.contract.upper())
                if spec is None:
                    sys.exit(f"Contrat inconnu : {args.contract} (dispo : {', '.join(propfirm.CONTRACTS)})")
                price = float(df["Close"].iloc[-1])
                sizing = propfirm.size_for_challenge(res.equity, price, args.capital, spec, rules)
                print(f"\n--- Dimensionnement prop firm ({args.prop}, capital {args.capital:,.0f}) ---\n")
                print(sizing.summary())
            else:
                daily = res.equity.resample("1D").last().dropna()
                daily = daily / daily.iloc[0]
                r = propfirm.evaluate(daily, rules)
                print(f"\n--- Challenge prop firm ({args.prop}) ---\n")
                print(r.summary())
    elif args.cmd == "signal":
        import time

        from . import live

        notifier = None
        if args.telegram:
            from . import notify

            notifier = notify.TelegramNotifier.from_env()
            if notifier is None:
                print("[telegram] désactivé : définis QUANTTERM_TG_TOKEN "
                      "et QUANTTERM_TG_CHAT.\n")

        last_notified: dict = {"key": None}

        def show_once() -> None:
            try:
                sig = live.compute(args.ticker, args.strategy, args.interval,
                                   k_stop=args.stop, k_target=args.target)
                print(sig.summary())
                # Notifier uniquement les signaux frais, une seule fois par barre.
                if notifier is not None and sig.fresh:
                    key = (sig.direction, sig.timestamp)
                    if key != last_notified["key"]:
                        if notifier.send(sig.summary()):
                            last_notified["key"] = key
            except Exception as exc:  # réseau capricieux : on n'interrompt pas la boucle
                print(f"[erreur] {exc}")

        if args.watch > 0:
            print(f"Signal live {args.ticker.upper()} / '{args.strategy}' {args.interval} "
                  f"— rafraîchi toutes les {args.watch}s (Ctrl+C pour arrêter)\n")
            try:
                while True:
                    show_once()
                    time.sleep(args.watch)
            except KeyboardInterrupt:
                print("\nArrêt du signal live.")
        else:
            show_once()
    elif args.cmd == "watch":
        import time

        from . import live

        notifier = None
        if args.telegram:
            from . import notify

            notifier = notify.TelegramNotifier.from_env()
            if notifier is None:
                print("[telegram] désactivé : définis QUANTTERM_TG_TOKEN "
                      "et QUANTTERM_TG_CHAT.\n")

        last_notified: dict = {}

        def cycle() -> None:
            for inst in live.INSTRUMENTS:
                try:
                    sig = live.compute(inst["ticker"], inst["strategy"], inst["interval"],
                                       k_stop=inst["k_stop"], k_target=inst["k_target"])
                    print(f"  • {inst['note']}")
                    print(sig.summary())
                    print()
                    if notifier is not None and sig.fresh:
                        key = (inst["ticker"], sig.direction, sig.timestamp)
                        if last_notified.get(inst["ticker"]) != key:
                            if notifier.send(f"{inst['ticker'].upper()}\n{sig.summary()}"):
                                last_notified[inst["ticker"]] = key
                except Exception as exc:  # réseau capricieux : on n'interrompt pas la boucle
                    print(f"  • {inst['ticker'].upper()} — [erreur] {exc}\n")

        tickers = ", ".join(i["ticker"].upper() for i in live.INSTRUMENTS)
        if args.every > 0:
            print(f"Watch multi-actif [{tickers}] — rafraîchi toutes les {args.every}s "
                  f"(Ctrl+C pour arrêter)\n")
            try:
                while True:
                    cycle()
                    time.sleep(args.every)
            except KeyboardInterrupt:
                print("\nArrêt du watch multi-actif.")
        else:
            print(f"Watch multi-actif [{tickers}]\n")
            cycle()
    elif args.cmd == "prop":
        from . import backtest, data, propfirm

        df = data.get_history(args.ticker, period=args.period)
        if args.scan:
            print(f"\nChallenges validés pour {args.ticker.upper()} ({args.period}) :\n")
            found = False
            for sn, strat in backtest.STRATEGIES.items():
                res = backtest.run(df, strat)
                for pn, rules in propfirm.PRESETS.items():
                    r = propfirm.evaluate(res.equity, rules, positions=res.positions)
                    if r.passed:
                        found = True
                        print(f"  ✓ {sn:9} / {pn:9} — {r.reason} "
                              f"(pire jour {r.worst_daily_loss:+.1%}, DD {r.max_drawdown:+.1%})")
            if not found:
                print("  Aucune combinaison ne valide sur cette période.")
        else:
            strat = backtest.STRATEGIES.get(args.strategy)
            rules = propfirm.PRESETS.get(args.preset)
            if strat is None:
                sys.exit(f"Stratégie inconnue : {args.strategy}")
            if rules is None:
                sys.exit(f"Preset inconnu : {args.preset} (dispo : {', '.join(propfirm.PRESETS)})")
            res = backtest.run(df, strat)
            r = propfirm.evaluate(res.equity, rules, positions=res.positions)
            print(f"\nProp firm — {args.ticker.upper()} / '{args.strategy}' / {args.preset} ({args.period})\n")
            print(r.summary())
    else:
        # Pas de sous-commande → interface TUI.
        from .app import main as run_app

        run_app()


if __name__ == "__main__":
    main()
