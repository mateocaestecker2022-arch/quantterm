"""Tests du screener : calcul des métriques et filtres, sans réseau.

On monkeypatch ``data.get_history`` pour servir des données synthétiques.
"""

from __future__ import annotations

import pandas as pd
import pytest

from quantterm import screener
from tests.conftest import make_ohlcv


@pytest.fixture
def fake_scan(monkeypatch):
    """Remplace le téléchargement par des DataFrames synthétiques déterministes."""
    universe = ["AAA", "BBB", "CCC"]

    def fake_get_history(ticker, period="1y", interval="1d", use_cache=True):
        seed = sum(ord(c) for c in ticker)
        return make_ohlcv(n=300, seed=seed)

    monkeypatch.setattr(screener.data, "get_history", fake_get_history)
    return universe


def test_scan_returns_all_tickers(fake_scan):
    df = screener.scan(universe=fake_scan)
    assert set(df.index) == {"AAA", "BBB", "CCC"}
    for col in ("price", "perf_1m", "rsi", "vol_ann", "trend"):
        assert col in df.columns


def test_scan_metrics_ranges(fake_scan):
    df = screener.scan(universe=fake_scan)
    assert (df["rsi"] >= 0).all() and (df["rsi"] <= 100).all()
    assert (df["price"] > 0).all()
    assert df["trend"].isin({"haussier", "baissier", "n/a"}).all()


def test_scan_skips_bad_tickers(monkeypatch):
    def raising(ticker, **kwargs):
        if ticker == "BAD":
            raise ValueError("no data")
        return make_ohlcv(seed=sum(ord(c) for c in ticker))

    monkeypatch.setattr(screener.data, "get_history", raising)
    df = screener.scan(universe=["GOOD", "BAD"])
    assert "GOOD" in df.index and "BAD" not in df.index


def test_filter_rsi_max(fake_scan):
    df = screener.scan(universe=fake_scan)
    filtered = screener.filter_screen(df, rsi_max=50)
    assert (filtered["rsi"] <= 50).all()


def test_filter_sort_descending(fake_scan):
    df = screener.scan(universe=fake_scan)
    filtered = screener.filter_screen(df, sort_by="perf_1m", ascending=False)
    perfs = filtered["perf_1m"].tolist()
    assert perfs == sorted(perfs, reverse=True)


def test_filter_trend(fake_scan):
    df = screener.scan(universe=fake_scan)
    haussier = screener.filter_screen(df, trend="haussier")
    assert (haussier["trend"] == "haussier").all()
