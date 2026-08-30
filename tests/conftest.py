"""Fixtures partagées : données OHLCV synthétiques, sans accès réseau.

On génère une série de prix reproductible (marche aléatoire avec tendance) pour
tester indicateurs, backtest et screener de façon déterministe et rapide.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_ohlcv(n: int = 300, seed: int = 42, start: float = 100.0) -> pd.DataFrame:
    """Construit un DataFrame OHLCV cohérent (High>=max(O,C), Low<=min(O,C))."""
    rng = np.random.default_rng(seed)
    # Rendements journaliers avec légère dérive haussière.
    rets = rng.normal(0.0005, 0.02, n)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start], close[:-1]])
    # Amplitude intrabar proportionnelle au prix.
    span = np.abs(rng.normal(0.0, 0.01, n)) * close
    high = np.maximum(open_, close) + span
    low = np.minimum(open_, close) - span
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)

    idx = pd.bdate_range("2023-01-02", periods=n, name="Date")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return make_ohlcv()


@pytest.fixture
def close(ohlcv: pd.DataFrame) -> pd.Series:
    return ohlcv["Close"]
