"""Tests de l'évaluation prop firm : validation, breachs, cas limites."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantterm import propfirm


def _equity(values: list[float]) -> pd.Series:
    idx = pd.bdate_range("2024-01-01", periods=len(values))
    return pd.Series(values, index=idx)


def test_pass_when_target_reached():
    rules = propfirm.PropFirmRules("t", profit_target=0.10, max_daily_loss=0.05,
                                   max_total_loss=0.10, min_trading_days=0)
    eq = _equity([1.0, 1.03, 1.06, 1.11])
    r = propfirm.evaluate(eq, rules)
    assert r.passed
    assert r.target_hit_day == 3


def test_fail_on_daily_loss():
    rules = propfirm.PropFirmRules("t", 0.10, 0.05, 0.20)
    # -6 % en une journée -> dépasse la perte journalière de 5 %.
    eq = _equity([1.0, 1.02, 0.958])
    r = propfirm.evaluate(eq, rules)
    assert not r.passed
    assert "journalière" in r.reason
    assert r.breach_day == 2


def test_fail_on_total_loss_static():
    rules = propfirm.PropFirmRules("t", 0.10, 0.10, 0.10)  # plancher à 0.90
    eq = _equity([1.0, 0.96, 0.92, 0.89])
    r = propfirm.evaluate(eq, rules)
    assert not r.passed
    assert "totale" in r.reason


def test_trailing_drawdown_breaches_after_peak():
    # Trailing 6 % : après un pic à 1.10, tomber sous 1.10*0.94 = 1.034 échoue.
    rules = propfirm.PropFirmRules("t", 0.30, 0.50, 0.06, trailing=True)
    eq = _equity([1.0, 1.10, 1.03])
    r = propfirm.evaluate(eq, rules)
    assert not r.passed
    assert "trailing" in r.reason.lower()


def test_min_trading_days_blocks_pass():
    rules = propfirm.PropFirmRules("t", 0.05, 0.10, 0.10, min_trading_days=10)
    eq = _equity([1.0, 1.06])  # objectif atteint mais 1 seul jour
    r = propfirm.evaluate(eq, rules)
    assert not r.passed
    assert r.target_hit_day == 1  # atteint mais non validé


def test_max_days_time_limit():
    rules = propfirm.PropFirmRules("t", 0.20, 0.50, 0.50, max_days=3)
    eq = _equity([1.0, 1.01, 1.02, 1.03, 1.04])  # jamais +20 %, delai depasse
    r = propfirm.evaluate(eq, rules)
    assert not r.passed
    assert "délai" in r.reason


def test_worst_daily_and_drawdown_tracked():
    rules = propfirm.PropFirmRules("t", 0.50, 0.50, 0.50)
    eq = _equity([1.0, 0.97, 1.02])  # jours : -3 %, +5.15 %
    r = propfirm.evaluate(eq, rules)
    assert r.worst_daily_loss == pytest.approx(-0.03, abs=1e-6)
    assert r.max_drawdown == pytest.approx(-0.03, abs=1e-6)


def test_presets_are_valid_rules():
    for name, rules in propfirm.PRESETS.items():
        assert 0 < rules.profit_target < 1
        assert 0 < rules.max_daily_loss < 1
        assert 0 < rules.max_total_loss < 1
