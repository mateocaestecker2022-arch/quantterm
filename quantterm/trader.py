"""Boucle de trading auto MT5 (compte démo) — exécution des signaux QuantTerm.

Principe : pour chaque instrument de :data:`quantterm.live.INSTRUMENTS`, on calcule
le signal **sur les bougies du broker** (feed cohérent avec l'exécution, pas yfinance),
et sur **signal frais** on ouvre une position dimensionnée en **risque fixe** (1 % par
défaut), avec :

- momentum (or, Ichimoku) : **SL + TP en ATR** posés sur l'ordre → sortie côté broker ;
- mean-reversion (nasdaq, RSI) : **SL protectif** seulement, sortie quand le signal
  repasse **FLAT** (retour à la moyenne) → fermeture par la boucle.

Sécurité : ``dry_run=True`` par défaut → tout est LOGGÉ, rien n'est envoyé. Il faut
``--live`` explicite pour armer. ``magic`` dédié : ne touche jamais aux autres algos.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import backtest, live
from . import indicators as ind
from .broker_mt5 import MT5Broker, compute_lot


@dataclass
class Decision:
    symbol: str
    action: str          # "OPEN" | "CLOSE" | "HOLD" | "SKIP"
    direction: int = 0
    lot: float = 0.0
    price: float = 0.0
    sl: float = 0.0
    tp: float | None = None
    reason: str = ""

    def line(self) -> str:
        if self.action == "OPEN":
            sens = "LONG" if self.direction == 1 else "SHORT"
            tp = f" TP {self.tp:.2f}" if self.tp else ""
            return (f"  {self.symbol:8} OPEN {sens} {self.lot:g} lot @ {self.price:.2f} "
                    f"SL {self.sl:.2f}{tp}  ({self.reason})")
        if self.action == "CLOSE":
            return f"  {self.symbol:8} CLOSE  ({self.reason})"
        return f"  {self.symbol:8} {self.action}  ({self.reason})"


def decide(broker: MT5Broker, inst: dict) -> Decision:
    """Décision pour un instrument (sans effet de bord : ne passe aucun ordre)."""
    symbol = inst["mt5_symbol"]
    df = broker.rates(symbol, inst["mt5_timeframe"], count=500)
    sig = live.from_df(symbol, df, inst["strategy"],
                       k_stop=inst["k_stop"], k_target=inst["k_target"])
    open_pos = broker.positions(symbol)
    pos = open_pos[0] if open_pos else None

    # 1) Position ouverte : gérer la sortie / le retournement.
    if pos is not None:
        # mean-rev : sortie au retour à la moyenne (signal devenu FLAT)
        if inst["exit_on_flat"] and sig.direction == 0:
            return Decision(symbol, "CLOSE", reason="retour à la moyenne (FLAT)")
        # signal frais opposé : on ferme (le nouveau sens sera pris au prochain tour)
        if sig.fresh and sig.direction == -pos.direction:
            return Decision(symbol, "CLOSE", reason="signal inverse frais")
        return Decision(symbol, "HOLD", direction=pos.direction,
                        reason="position en cours")

    # 2) Pas de position : n'entrer que sur signal FRAIS et directionnel.
    if not (sig.fresh and sig.direction != 0):
        return Decision(symbol, "HOLD", reason="pas de signal frais")

    info = broker.symbol_info(symbol)
    stop_dist = inst["k_stop"] * sig.atr
    lot = compute_lot(
        balance=broker.balance(), risk_pct=inst["risk_pct"], stop_distance=stop_dist,
        tick_size=info.trade_tick_size, tick_value=info.trade_tick_value,
        volume_min=info.volume_min, volume_step=info.volume_step,
        volume_max=info.volume_max, max_lot=inst.get("max_lot"),
    )
    if lot <= 0:
        return Decision(symbol, "SKIP", reason="lot < volume_min (risque trop petit)")

    entry = sig.price
    d = sig.direction
    sl = entry - d * stop_dist
    tp = None if inst["exit_on_flat"] else entry + d * inst["k_target"] * sig.atr
    return Decision(symbol, "OPEN", direction=d, lot=lot, price=entry,
                    sl=sl, tp=tp, reason="signal frais")


def execute(broker: MT5Broker, inst: dict, dec: Decision) -> str:
    """Applique une décision côté broker. Retourne un statut lisible."""
    if dec.action == "OPEN":
        r = broker.market_order(dec.symbol, dec.direction, dec.lot, dec.sl, dec.tp)
        return _order_status(broker, r)
    if dec.action == "CLOSE":
        for pos in broker.positions(dec.symbol):
            r = broker.close(pos)
            return _order_status(broker, r)
    return "—"


def _order_status(broker: MT5Broker, result) -> str:
    if result is None:
        return f"échec order_send : {broker.mt5.last_error()}"
    ok = result.retcode == broker.mt5.TRADE_RETCODE_DONE
    return f"{'OK' if ok else 'REJET'} retcode={result.retcode}"


def run_once(broker: MT5Broker, dry_run: bool = True) -> list[Decision]:
    """Un cycle sur tous les instruments. Retourne les décisions (pour log/tests)."""
    decisions = []
    for inst in live.INSTRUMENTS:
        try:
            dec = decide(broker, inst)
        except Exception as exc:  # réseau/broker capricieux : on n'arrête pas la boucle
            print(f"  {inst['mt5_symbol']:8} [erreur] {exc}")
            continue
        line = dec.line()
        if dec.action in ("OPEN", "CLOSE"):
            if dry_run:
                print(f"{line}   [DRY-RUN — non envoyé]")
            else:
                status = execute(broker, inst, dec)
                print(f"{line}   -> {status}")
        else:
            print(line)
        decisions.append(dec)
    return decisions
