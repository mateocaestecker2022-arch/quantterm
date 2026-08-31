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


# --------------------------------------------------------------------------- #
# Dimensionnement (size_for_challenge)
# --------------------------------------------------------------------------- #

def _intraday_equity(worst_dd: float, n_days: int = 8) -> pd.Series:
    """Equity intraday synthétique : monte régulièrement, avec un creux ``worst_dd``
    (fraction <= 0) au milieu — pour piloter le pire drawdown/jour du notionnel."""
    idx = pd.date_range("2024-01-01 09:00", periods=n_days * 4, freq="h")
    vals = np.linspace(1.0, 1.20, len(idx))          # tendance haussière
    vals[len(idx) // 2] *= (1.0 + worst_dd)          # un creux ponctuel
    return pd.Series(vals, index=idx)


def test_sizing_respects_both_limits():
    rules = propfirm.PropFirmRules("t", 0.08, 0.05, 0.10)
    eq = _intraday_equity(worst_dd=-0.02)            # pire creux -2 % du notionnel
    spec = propfirm.CONTRACTS["MGC"]                 # 10 oz
    s = propfirm.size_for_challenge(eq, price=1000.0, capital=100_000, contract=spec, rules=rules)
    # La perte ramenée au compte doit rester sous les deux limites.
    assert abs(s.worst_daily_acct) <= rules.max_daily_loss + 1e-9
    assert abs(s.worst_dd_acct) <= rules.max_total_loss + 1e-9
    # Un contrat de plus dépasserait forcément une des deux règles.
    over = (s.n_contracts + 1) * spec.multiplier * 1000.0 / 100_000
    assert abs(-0.02 * over) > rules.max_total_loss - 1e-9 or \
        abs(s.worst_daily_acct / s.leverage * over) > rules.max_daily_loss - 1e-9


def test_sizing_scales_with_capital():
    rules = propfirm.PropFirmRules("t", 0.08, 0.05, 0.10)
    eq = _intraday_equity(worst_dd=-0.03)
    spec = propfirm.CONTRACTS["MGC"]
    small = propfirm.size_for_challenge(eq, 1000.0, 20_000, spec, rules)
    big = propfirm.size_for_challenge(eq, 1000.0, 200_000, spec, rules)
    assert big.n_contracts > small.n_contracts


def test_sizing_impossible_returns_zero():
    rules = propfirm.PropFirmRules("t", 0.08, 0.05, 0.10)
    eq = _intraday_equity(worst_dd=-0.10)            # gros risque par unité de notionnel
    spec = propfirm.CONTRACTS["GC"]                  # gros contrat (100 oz)
    # Capital minuscule : même 1 contrat dépasse les règles.
    s = propfirm.size_for_challenge(eq, 5000.0, 1000, spec, rules)
    assert s.n_contracts == 0
    assert s.verdict is None
