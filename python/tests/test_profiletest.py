# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import profiletest as pt  # noqa: E402
from klarfarbe.oklab import oklab_to_srgb, srgb_to_oklab  # noqa: E402


def test_caps_inside_srgb_gamut():
    for r in pt.CHROMA:
        rgb = pt.caps(r)
        assert rgb.shape == (pt.N_CAPS + 1, 3)
        assert np.abs(oklab_to_srgb(srgb_to_oklab(rgb)) - rgb).max() < 1e-5


def test_perfect_order_scores_one():
    perfect = list(range(1, pt.N_CAPS + 1))
    for r in pt.CHROMA:
        ci, _ = pt.confusion_index(perfect, r)
        assert ci == pytest.approx(1.0)


def test_reversed_order_also_scores_one():
    # starting the other way round the circle is not an error
    ci, _ = pt.confusion_index(list(range(pt.N_CAPS, 0, -1)), "saturated")
    assert ci < 1.3


def test_normal_observer_passes():
    rng = np.random.default_rng(1)
    for _ in range(20):
        res = pt.evaluate(pt.simulated_order("saturated", None, 0, rng),
                          pt.simulated_order("pale", None, 0, rng))
        assert res["type"] == "unknown" and res["severity"] == 0.3


@pytest.mark.parametrize("type_", ["protan", "deutan"])
def test_strong_deficiency_detected_with_type(type_):
    rng = np.random.default_rng(2)
    results = [pt.evaluate(pt.simulated_order("saturated", type_, 1.0, rng),
                           pt.simulated_order("pale", type_, 1.0, rng)) for _ in range(100)]
    assert all(r["severity"] == 0.85 for r in results)
    correct = np.mean([r["type"] == type_ for r in results])
    wrong = np.mean([r["type"] not in (type_, "unknown") for r in results])
    assert correct >= 0.8
    assert wrong <= 0.06  # the test may say "unsure", but rarely the wrong type


def test_moderate_deficiency_caught_by_pale_round_without_guessing_type():
    rng = np.random.default_rng(3)
    results = [pt.evaluate(pt.simulated_order("saturated", "deutan", 0.7, rng),
                           pt.simulated_order("pale", "deutan", 0.7, rng)) for _ in range(40)]
    assert np.mean([r["severity"] >= 0.6 for r in results]) > 0.75
    pale_only = [r for r in results if r["severity"] == 0.6]
    assert all(r["type"] == "unknown" for r in pale_only)


def test_suggested_profile_uses_fallback():
    res = {"type": "unknown", "severity": 0.6}
    assert pt.suggested_profile(res, "protan").type == "protan"
