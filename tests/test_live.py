"""Tests du signal live (cœur pur ``from_df``, sans réseau)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantterm import live


def test_signal_direction_matches_strategy(ohlcv):
    sig = live.from_df("TEST", ohlcv, "ichimoku")
    # La direction correspond à la dernière position cible de la stratégie.
    from quantterm import backtest
    expected = int(backtest.STRATEGIES["ichimoku"](ohlcv).iloc[-1])
    assert sig.direction == expected
    assert sig.label in {"LONG", "SHORT", "FLAT"}
    assert sig.ticker == "TEST"


def test_stop_target_placed_correctly_for_long():
    # Série qui force un LONG frais sur la dernière barre via une stratégie custom.
    idx = pd.date_range("2024-01-01 09:00", periods=5, freq="5min")
    df = pd.DataFrame(
        {"Open": [10, 10, 10, 10, 10.0], "High": [11, 11, 11, 11, 11.0],
         "Low": [9, 9, 9, 9, 9.0], "Close": [10, 10, 10, 10, 10.0],
         "Volume": [1, 1, 1, 1, 1]},
        index=idx,
    )
    from quantterm import backtest
    backtest.STRATEGIES["_tmp_long"] = lambda d: pd.Series(
        [0, 0, 0, 0, 1.0], index=d.index
    )
    try:
        sig = live.from_df("X", df, "_tmp_long", k_stop=2.0, k_target=3.0)
    finally:
        del backtest.STRATEGIES["_tmp_long"]
    assert sig.direction == 1
    assert sig.fresh is True
    # stop en-dessous, target au-dessus du prix pour un long.
    assert sig.stop_price < sig.price < sig.target_price
    assert sig.stop_price == pytest.approx(sig.price - 2.0 * sig.atr)
    assert sig.target_price == pytest.approx(sig.price + 3.0 * sig.atr)


def test_flat_has_no_levels():
    # Ichimoku sur un historique trop court -> toutes les lignes NaN -> flat.
    idx = pd.date_range("2024-01-01", periods=3, freq="5min")
    df = pd.DataFrame(
        {"Open": [1, 1, 1.0], "High": [1, 1, 1.0], "Low": [1, 1, 1.0],
         "Close": [1, 1, 1.0], "Volume": [1, 1, 1]},
        index=idx,
    )
    sig = live.from_df("X", df, "ichimoku")
    assert sig.direction == 0
    assert sig.stop_price is None and sig.target_price is None


def test_unknown_strategy_raises(ohlcv):
    with pytest.raises(ValueError):
        live.from_df("X", ohlcv, "n_existe_pas")
