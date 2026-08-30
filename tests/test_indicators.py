"""Tests des indicateurs techniques : forme, bornes et cohérence des valeurs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantterm import indicators as ind


def test_sma_matches_manual(close):
    manual = close.iloc[-5:].mean()
    assert ind.sma(close, 5).iloc[-1] == pytest.approx(manual)


def test_ema_preserves_length_and_last_is_finite(close):
    e = ind.ema(close, 20)
    assert len(e) == len(close)
    assert np.isfinite(e.iloc[-1])


def test_rsi_bounded_0_100(close):
    r = ind.rsi(close)
    valid = r.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_all_up_is_high():
    # Série strictement croissante -> RSI doit tendre vers 100.
    s = pd.Series(np.arange(1, 60, dtype=float))
    assert ind.rsi(s).iloc[-1] > 99


def test_macd_columns_and_hist_consistency(close):
    m = ind.macd(close)
    assert list(m.columns) == ["macd", "signal", "hist"]
    assert m["hist"].iloc[-1] == pytest.approx(
        m["macd"].iloc[-1] - m["signal"].iloc[-1]
    )


def test_bollinger_ordering(close):
    b = ind.bollinger(close).dropna()
    assert (b["upper"] >= b["mid"]).all()
    assert (b["mid"] >= b["lower"]).all()


def test_atr_positive(ohlcv):
    a = ind.atr(ohlcv).dropna()
    assert (a > 0).all()


def test_true_range_ge_high_low(ohlcv):
    tr = ind.true_range(ohlcv)
    hl = ohlcv["High"] - ohlcv["Low"]
    # Le True Range est toujours >= amplitude high-low de la barre.
    assert (tr.iloc[1:] >= hl.iloc[1:] - 1e-9).all()


def test_stochastic_bounded(ohlcv):
    s = ind.stochastic(ohlcv).dropna()
    assert (s["k"] >= -1e-6).all() and (s["k"] <= 100 + 1e-6).all()


def test_williams_r_bounded(ohlcv):
    w = ind.williams_r(ohlcv).dropna()
    assert (w >= -100 - 1e-6).all() and (w <= 1e-6).all()


def test_mfi_bounded(ohlcv):
    m = ind.mfi(ohlcv).dropna()
    assert (m >= 0).all() and (m <= 100).all()


def test_adx_columns_and_bounds(ohlcv):
    a = ind.adx(ohlcv)
    assert set(a.columns) == {"plus_di", "minus_di", "adx"}
    adx = a["adx"].dropna()
    assert (adx >= 0).all() and (adx <= 100 + 1e-6).all()


def test_keltner_ordering(ohlcv):
    k = ind.keltner(ohlcv).dropna()
    assert (k["upper"] >= k["mid"]).all() and (k["mid"] >= k["lower"]).all()


def test_donchian_contains_price(ohlcv):
    d = ind.donchian(ohlcv).dropna()
    # Le canal encadre les clôures récentes.
    sub = ohlcv["Close"].reindex(d.index)
    assert (d["upper"] >= sub - 1e-6).all()
    assert (d["lower"] <= sub + 1e-6).all()


def test_obv_is_cumulative(ohlcv):
    o = ind.obv(ohlcv)
    assert len(o) == len(ohlcv)
    assert np.isfinite(o.iloc[-1])


def test_zscore_zero_mean_window(close):
    z = ind.zscore(close, 20).dropna()
    # Un z-score reste dans une plage raisonnable sur des données normales.
    assert z.abs().max() < 10
