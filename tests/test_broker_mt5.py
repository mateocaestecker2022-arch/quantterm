"""Tests du sizing en risque fixe (fonction pure, sans MT5 ni réseau)."""

from __future__ import annotations

import pytest

from quantterm.broker_mt5 import compute_lot


# Symbole type "or" : tick 0.01, un tick vaut 1$ pour 1 lot (100 oz).
GOLD = dict(tick_size=0.01, tick_value=1.0, volume_min=0.01,
            volume_step=0.01, volume_max=100.0)


def test_lot_risks_the_target_amount():
    # balance 10 000, risque 1 % = 100$. Stop 3.0 en prix = 300 ticks.
    # perte/lot = 300 * 1$ = 300$ -> lot = 100/300 = 0.333 -> arrondi step 0.01 = 0.33.
    lot = compute_lot(10_000, 0.01, stop_distance=3.0, **GOLD)
    assert lot == pytest.approx(0.33)
    # La perte réelle au stop reste <= au risque visé (arrondi vers le bas).
    loss = (3.0 / GOLD["tick_size"]) * GOLD["tick_value"] * lot
    assert loss <= 10_000 * 0.01


def test_wider_stop_gives_smaller_lot():
    tight = compute_lot(10_000, 0.01, stop_distance=2.0, **GOLD)
    wide = compute_lot(10_000, 0.01, stop_distance=6.0, **GOLD)
    assert wide < tight


def test_skips_when_risk_below_min_lot():
    # Petit capital + gros stop -> lot théorique < volume_min -> 0.0 (on saute).
    assert compute_lot(100, 0.01, stop_distance=50.0, **GOLD) == 0.0


def test_respects_max_lot_cap():
    lot = compute_lot(1_000_000, 0.01, stop_distance=1.0, max_lot=2.0, **GOLD)
    assert lot == 2.0


def test_zero_on_invalid_inputs():
    assert compute_lot(0, 0.01, 3.0, **GOLD) == 0.0
    assert compute_lot(10_000, 0.01, 0.0, **GOLD) == 0.0
    assert compute_lot(10_000, 0.0, 3.0, **GOLD) == 0.0
