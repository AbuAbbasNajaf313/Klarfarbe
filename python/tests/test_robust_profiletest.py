# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Robustness test: Monte-Carlo robustness of the colour arrangement test."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import profiletest as pt  # noqa: E402

N = 200


def _runs(type_, sev, n, seed):
    rng = np.random.default_rng(seed)
    return [pt.evaluate(pt.simulated_order("saturated", type_, sev, rng),
                        pt.simulated_order("pale", type_, sev, rng)) for _ in range(n)]


def test_normal_observer_false_positive_rate_at_calibrated_noise():
    res = _runs(None, 0, N, 11)
    fp = np.mean([r["severity"] > 0.3 for r in res])
    assert fp <= 0.03  # measured 0.7 %
    assert not any(r["severity"] == 0.85 for r in res)


@pytest.mark.parametrize("t", ["protan", "deutan"])
def test_strong_never_missed_at_calibrated_noise(t):
    res = _runs(t, 1.0, N, 12)
    assert all(r["severity"] == 0.85 for r in res)


def test_moderate_mostly_detected_at_calibrated_noise():
    res = _runs("deutan", 0.7, N, 13)
    # caps since v0.2 closer to the D-15 and stricter rule (robust to noise):
    # measured 79 % (v0.1: 89 %, but 30 % false alarms at 1.7 x noise)
    assert np.mean([r["severity"] >= 0.6 for r in res]) > 0.72


def test_moderate_type_errors_bounded():
    res = _runs("deutan", 0.7, N, 14) + _runs("protan", 0.7, N, 15)
    wrong = np.mean([r["type"] in ("protan", "deutan") and r["type"] != t
                     for r, t in zip(res, ["deutan"] * N + ["protan"] * N)])
    assert wrong < 0.15  # measured ~7 %


def test_false_positive_rate_robust_to_more_noise(monkeypatch):
    monkeypatch.setattr(pt, "SIM_NOISE", 0.010)
    res = _runs(None, 0, N, 21)
    assert np.mean([r["severity"] > 0.3 for r in res]) < 0.10


def test_random_clicking_does_not_yield_confident_type():
    rng = np.random.default_rng(3)
    res = [pt.evaluate(list(rng.permutation(15) + 1), list(rng.permutation(15) + 1)) for _ in range(500)]
    assert np.mean([r["type"] != "unknown" for r in res]) < 0.05


def test_selectivity_index_separates_random_from_cvd():
    """Basis for the proposed fix: S = major/minor of Vingrys & King-Smith."""
    rng = np.random.default_rng(4)
    caps = pt.caps("saturated")

    def s_index(o):
        m = pt.moments(o, caps)
        return m["major"] / max(m["minor"], 1e-9)

    rnd = np.array([s_index(list(rng.permutation(15) + 1)) for _ in range(500)])
    cvd = np.array([s_index(pt.simulated_order("saturated", t, 1.0, rng))
                    for t in ("protan", "deutan") for _ in range(150)])
    assert np.mean(rnd > 1.8) < 0.05 and np.mean(cvd > 1.8) > 0.97


@pytest.mark.parametrize("order", [[1] * 15, list(range(1, 15)), list(range(0, 15)), []],
                         ids=["duplicates", "14caps", "with-reference", "empty"])
def test_evaluate_rejects_invalid_orders(order):
    with pytest.raises(ValueError):
        with np.errstate(all="ignore"):
            pt.evaluate(order, list(range(1, 16)))


def test_evaluate_out_of_range_index_raises():
    with pytest.raises((ValueError, IndexError)):
        pt.evaluate(list(range(2, 17)), list(range(1, 16)))


def test_confusion_angle_finite_and_in_range():
    rng = np.random.default_rng(8)
    o = pt.simulated_order("saturated", "protan", 1.0, rng)
    ci1, a1 = pt.confusion_index(o, "saturated")
    assert np.isfinite(ci1) and -90 <= a1 < 90
