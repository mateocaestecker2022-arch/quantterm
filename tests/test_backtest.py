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


# --------------------------------------------------------------------------- #
# Backtest événementiel intra-barre
# --------------------------------------------------------------------------- #

def test_intrabar_runs_and_is_consistent(ohlcv):
    result = backtest.run_intrabar(ohlcv, backtest.STRATEGIES["ichimoku"])
    assert len(result.equity) == len(ohlcv)
    assert np.isfinite(result.equity.iloc[-1])
    # Les positions ne prennent que les valeurs -1/0/1.
    assert set(result.positions.unique()).issubset({-1.0, 0.0, 1.0})
    # Nombre de trades cohérent entre la série et la métrique.
    assert result.metrics["n_trades"] == len(result.trades)
    for key in ("total_return", "sharpe", "max_drawdown", "win_rate", "per_trade"):
        assert np.isfinite(result.metrics[key])


def test_intrabar_stop_caps_the_loss():
    # Entrée long forcée puis krach : le stop doit plafonner la perte bien avant
    # la clôture effondrée (98 vs 90).
    df = pd.DataFrame(
        {
            "Open":  [100, 100, 100, 95, 95, 95.0],
            "High":  [100, 100, 101, 95, 95, 95.0],
            "Low":   [100, 100, 99, 90, 90, 90.0],
            "Close": [100, 100, 100, 90, 90, 90.0],
            "Volume": [1, 1, 1, 1, 1, 1],
        }
    )
    # Signal : transition vers long à la barre 1 -> entrée à l'open de la barre 2.
    desired = pd.Series([0, 1, 1, 1, 1, 1.0], index=df.index)
    res = backtest.run_intrabar(
        df, lambda d: desired, fee=0.0, atr_window=1, k_stop=1.0, k_target=10.0,
    )
    # ATR(2)=2 -> stop=98. Un seul trade, sorti au stop : -2 %, pas -10 %.
    assert res.metrics["n_trades"] == 1
    assert res.trades.iloc[0] == pytest.approx(-0.02)
    assert res.equity.min() >= 0.98 - 1e-9  # la perte est bien plafonnée


def test_intrabar_no_entry_without_fresh_signal():
    # Un signal long CONSTANT (jamais de transition) ne doit jamais entrer.
    df = pd.DataFrame(
        {
            "Open":  [100, 101, 102, 103.0],
            "High":  [101, 102, 103, 104.0],
            "Low":   [99, 100, 101, 102.0],
            "Close": [100, 101, 102, 103.0],
            "Volume": [1, 1, 1, 1],
        }
    )
    res = backtest.run_intrabar(
        df, lambda d: pd.Series(1.0, index=d.index), fee=0.0, atr_window=1,
    )
    assert res.metrics["n_trades"] == 0
    assert res.equity.iloc[-1] == pytest.approx(1.0)
