"""Tests du moteur de backtest : absence de look-ahead, coûts, métriques."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantterm import backtest


def test_all_strategies_run(ohlcv):
    for name, strat in backtest.STRATEGIES.items():
        result = backtest.run(ohlcv, strat)
        assert len(result.equity) == len(ohlcv)
        assert np.isfinite(result.equity.iloc[-1])
        # Toutes les métriques attendues sont présentes et finies.
        for key in ("total_return", "cagr", "sharpe", "max_drawdown", "win_rate"):
            assert np.isfinite(result.metrics[key]), (name, key)


def test_buy_and_hold_matches_asset_return(ohlcv):
    # Sans frais, buy & hold doit reproduire le rendement de l'actif.
    result = backtest.run(ohlcv, backtest.STRATEGIES["hold"], fee=0.0)
    asset_total = ohlcv["Close"].iloc[-1] / ohlcv["Close"].iloc[0] - 1
    assert result.metrics["total_return"] == pytest.approx(asset_total, rel=1e-6)


def test_no_lookahead():
    # Stratégie qui "triche" en regardant la barre courante : le moteur décale
    # la position d'une barre, donc le signal parfait ne doit PAS être exploité
    # sur la barre où il est connu.
    df = pd.DataFrame(
        {
            "Open": [10, 10, 10, 10],
            "High": [10, 10, 10, 10],
            "Low": [10, 10, 10, 10],
            "Close": [10.0, 11.0, 10.0, 12.0],
            "Volume": [1, 1, 1, 1],
        }
    )

    def perfect(d):
        # Vise long uniquement sur la barre 1 (celle qui monte de 10->11).
        pos = pd.Series(0.0, index=d.index)
        pos.iloc[1] = 1.0
        return pos

    result = backtest.run(df, perfect, fee=0.0)
    # La position est appliquée à t+1 (barre 2), dont le rendement est négatif.
    # Le rendement de la stratégie sur barre 2 = -1/11, pas +1/10.
    assert result.returns.iloc[2] == pytest.approx(-1.0 / 11.0)
    assert result.returns.iloc[1] == 0.0  # rien n'est capté sur la barre du signal


def test_fees_reduce_return(ohlcv):
    strat = backtest.STRATEGIES["macd"]  # stratégie qui trade souvent
    no_fee = backtest.run(ohlcv, strat, fee=0.0).metrics["total_return"]
    with_fee = backtest.run(ohlcv, strat, fee=0.01).metrics["total_return"]
    assert with_fee < no_fee


def test_flat_position_yields_no_return():
    df = pd.DataFrame(
        {
            "Open": [1, 2, 3.0],
            "High": [1, 2, 3.0],
            "Low": [1, 2, 3.0],
            "Close": [1, 2, 3.0],
            "Volume": [1, 1, 1],
        }
    )
    result = backtest.run(df, lambda d: pd.Series(0.0, index=d.index), fee=0.0)
    assert result.equity.iloc[-1] == pytest.approx(1.0)
    assert result.metrics["n_trades"] == 0
