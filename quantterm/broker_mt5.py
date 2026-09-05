"""Pont d'exécution MetaTrader 5 (compte démo).

Connexion par **path + login** (le terminal MT5 est lancé/pointé explicitement),
credentials lus dans l'environnement — jamais en argument CLI, pour ne pas fuiter :

    QUANTTERM_MT5_PATH      chemin du terminal64.exe (ou du terminal sous Wine)
    QUANTTERM_MT5_LOGIN     numéro de compte (int)
    QUANTTERM_MT5_PASSWORD  mot de passe
    QUANTTERM_MT5_SERVER    serveur (ex. "MetaQuotes-Demo")

Le package ``MetaTrader5`` n'existe que là où tourne le terminal (Windows / Wine) :
import **paresseux** pour que le reste du projet (tests, TUI) s'importe sans lui.

⚠️ 1 terminal par processus Python : ce bot tourne dans SON process, avec un
``magic`` dédié pour ne jamais toucher aux positions des autres algos.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import pandas as pd

# Colonnes OHLCV normalisées (mêmes que quantterm.data).
OHLCV = ["Open", "High", "Low", "Close", "Volume"]


# --------------------------------------------------------------------------- #
# Sizing : lot en risque fixe (fonction PURE, testable sans MT5)
# --------------------------------------------------------------------------- #
def compute_lot(
    balance: float,
    risk_pct: float,
    stop_distance: float,       # distance du stop en PRIX (ex. k_stop * ATR)
    tick_size: float,
    tick_value: float,          # valeur monétaire d'un tick pour 1 lot
    volume_min: float,
    volume_step: float,
    volume_max: float,
    max_lot: float | None = None,
) -> float:
    """Retourne le lot qui risque ``risk_pct`` du capital si le stop est touché.

    ``0.0`` = trade à sauter (risque trop petit pour ``volume_min``, ou entrées
    invalides). Le lot est **arrondi au step inférieur** (jamais sur-risquer),
    plafonné à ``max_lot``/``volume_max``.
    """
    if min(stop_distance, tick_size, tick_value, risk_pct, balance) <= 0:
        return 0.0
    money_risk = balance * risk_pct
    loss_per_lot = (stop_distance / tick_size) * tick_value
    if loss_per_lot <= 0:
        return 0.0
    raw = money_risk / loss_per_lot
    steps = math.floor(raw / volume_step)
    lot = steps * volume_step
    if max_lot is not None:
        lot = min(lot, max_lot)
    lot = min(lot, volume_max)
    if lot < volume_min:
        return 0.0
    return round(lot, 8)


# --------------------------------------------------------------------------- #
# Broker
# --------------------------------------------------------------------------- #
@dataclass
class Position:
    ticket: int
    symbol: str
    direction: int     # 1 long, -1 short
    volume: float
    price_open: float


class MT5Broker:
    """Enveloppe fine autour du package ``MetaTrader5``."""

    _TF = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
           "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
           "D1": "TIMEFRAME_D1"}

    def __init__(self, magic: int):
        self.magic = magic
        self._mt5 = None

    @property
    def mt5(self):
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5  # import paresseux
            except ImportError as exc:  # pragma: no cover - dépend de l'env
                raise RuntimeError(
                    "Package 'MetaTrader5' introuvable — à installer dans l'env qui "
                    "fait tourner le terminal (Windows / Wine)."
                ) from exc
            self._mt5 = mt5
        return self._mt5

    # -- connexion --------------------------------------------------------- #
    def connect(self) -> None:
        path = os.environ.get("QUANTTERM_MT5_PATH")
        login = os.environ.get("QUANTTERM_MT5_LOGIN")
        password = os.environ.get("QUANTTERM_MT5_PASSWORD")
        server = os.environ.get("QUANTTERM_MT5_SERVER")
        missing = [k for k, v in {
            "QUANTTERM_MT5_PATH": path, "QUANTTERM_MT5_LOGIN": login,
            "QUANTTERM_MT5_PASSWORD": password, "QUANTTERM_MT5_SERVER": server,
        }.items() if not v]
        if missing:
            raise RuntimeError(f"Variables d'env manquantes : {', '.join(missing)}")

        if not self.mt5.initialize(path=path):
            raise RuntimeError(f"initialize() a échoué : {self.mt5.last_error()}")
        if not self.mt5.login(int(login), password=password, server=server):
            err = self.mt5.last_error()
            self.mt5.shutdown()
            raise RuntimeError(f"login() a échoué : {err}")

    def shutdown(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()

    # -- lecture ----------------------------------------------------------- #
    def balance(self) -> float:
        info = self.mt5.account_info()
        if info is None:
            raise RuntimeError(f"account_info() indisponible : {self.mt5.last_error()}")
        return float(info.balance)

    def symbol_info(self, symbol: str):
        if not self.mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Symbole indisponible : {symbol} ({self.mt5.last_error()})")
        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"symbol_info({symbol}) vide : {self.mt5.last_error()}")
        return info

    def rates(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        """Bougies OHLCV du BROKER (feed cohérent avec l'exécution)."""
        self.symbol_info(symbol)  # s'assure que le symbole est sélectionné
        tf = getattr(self.mt5, self._TF[timeframe])
        arr = self.mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if arr is None or len(arr) == 0:
            raise RuntimeError(f"Pas de bougies pour {symbol} ({self.mt5.last_error()})")
        df = pd.DataFrame(arr)
        df["Date"] = pd.to_datetime(df["time"], unit="s")
        out = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                 "close": "Close", "tick_volume": "Volume"})
        return out.set_index("Date")[OHLCV]

    def positions(self, symbol: str | None = None) -> list[Position]:
        """Positions ouvertes de CE bot (filtrées par magic)."""
        raw = self.mt5.positions_get(symbol=symbol) if symbol else self.mt5.positions_get()
        out = []
        for p in raw or []:
            if p.magic != self.magic:
                continue
            direction = 1 if p.type == self.mt5.POSITION_TYPE_BUY else -1
            out.append(Position(p.ticket, p.symbol, direction, p.volume, p.price_open))
        return out

    # -- ordres ------------------------------------------------------------ #
    def market_order(self, symbol: str, direction: int, lot: float,
                     sl: float, tp: float | None, comment: str = "quantterm"):
        tick = self.mt5.symbol_info_tick(symbol)
        is_buy = direction == 1
        price = tick.ask if is_buy else tick.bid
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": self.mt5.ORDER_TYPE_BUY if is_buy else self.mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": float(sl),
            "tp": float(tp) if tp else 0.0,
            "deviation": 20,
            "magic": self.magic,
            "comment": comment,
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }
        return self.mt5.order_send(request)

    def close(self, pos: Position, comment: str = "quantterm-close"):
        tick = self.mt5.symbol_info_tick(pos.symbol)
        is_buy_close = pos.direction == -1  # fermer un short = acheter
        price = tick.ask if is_buy_close else tick.bid
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "position": pos.ticket,
            "volume": pos.volume,
            "type": self.mt5.ORDER_TYPE_BUY if is_buy_close else self.mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 20,
            "magic": self.magic,
            "comment": comment,
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }
        return self.mt5.order_send(request)
