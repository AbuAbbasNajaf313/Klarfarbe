# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Benefit check: with Klarfarbe, colour pairs must be easier to tell apart
for simulated protan and deutan observers than without it.

Metric: Oklab distance of the two colours *as the simulated observer sees
them* (Machado et al. 2009 for anomalous trichromacy, blended with identity
as in profiletest.simulate; Vienot, Brettel & Mollon 1999 for dichromacy).
These are model values, not results from people.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile, snap_srgb  # noqa: E402
from klarfarbe.categories import CATEGORIES  # noqa: E402
from klarfarbe.oklab import lab_to_lch, lch_to_lab, linear_to_srgb, oklab_to_srgb, srgb_to_linear, srgb_to_oklab  # noqa: E402
from klarfarbe.profiletest import simulate  # noqa: E402

# Vienot, Brettel & Mollon (1999), linear RGB -> LMS
_RGB2LMS = np.array([[17.8824, 43.5161, 4.11935],
                     [3.45565, 27.1554, 3.86714],
                     [0.0299566, 0.184309, 1.46709]])
_LMS2RGB = np.linalg.inv(_RGB2LMS)


def vienot(rgb, t):
    lms = srgb_to_linear(np.clip(rgb, 0, 1)) @ _RGB2LMS.T
    if t == "protan":
        lms[..., 0] = 2.02344 * lms[..., 1] - 2.52581 * lms[..., 2]
    else:
        lms[..., 1] = 0.494207 * lms[..., 0] + 1.24827 * lms[..., 2]
    return linear_to_srgb(np.clip(lms @ _LMS2RGB.T, 0, 1))


def seen(rgb, t, s, model):
    if model == "vienot":
        return srgb_to_oklab(vienot(rgb, t))
    return srgb_to_oklab(np.clip(simulate(np.clip(rgb, 0, 1), t, s), 0, 1))


KEYS = [c.key for c in CATEGORIES if c.snaps]
PROTO = np.array([c.prototype_srgb for c in CATEGORIES if c.snaps]) / 255.0
_lch = lab_to_lch(srgb_to_oklab(PROTO))
_lch[:, 1] *= 0.55
_lch[:, 0] -= 0.08
MUTED = np.clip(oklab_to_srgb(lch_to_lab(_lch)), 0, 1)
CRITICAL = [("red", "green"), ("red", "brown"), ("green", "brown"), ("orange", "green"), ("green", "yellow"),
            ("purple", "blue"), ("red", "orange"), ("blue", "green"), ("pink", "purple"), ("orange", "brown")]
RED_GREEN = ((200, 30, 30), (30, 160, 60))
RED_GREY = ((180, 60, 60), (100, 100, 100))
GREEN_GREY = ((60, 150, 60), (125, 125, 125))
CASES = [(t, s, m) for t in ("protan", "deutan") for s, m in ((0.5, "machado"), (1.0, "machado"), (1.0, "vienot"))]


def _snap(prof):
    return (lambda x: x) if prof is None else (lambda x: snap_srgb(x, prof))


def worst_pair(prof, t, s, model):
    f = _snap(prof)
    worst = np.inf
    for base in (PROTO, MUTED):
        x = seen(f(base), t, s, model)
        for a, b in CRITICAL:
            worst = min(worst, np.linalg.norm(x[KEYS.index(a)] - x[KEYS.index(b)]))
    return worst


def pair(prof, t, s, model, ab):
    f = _snap(prof)
    a, b = (seen(f(np.array(c) / 255.0), t, s, model) for c in ab)
    return float(np.linalg.norm(a - b))


@pytest.mark.parametrize("t,s,model", CASES)
def test_worst_critical_pair_improves(t, s, model):
    without = worst_pair(None, t, s, model)
    with_ = worst_pair(Profile.default_for(t, s), t, s, model)
    assert with_ > without + 0.01, (without, with_)


@pytest.mark.parametrize("t,s,model", CASES)
@pytest.mark.parametrize("name,ab", [("red-green", RED_GREEN), ("red-grey", RED_GREY), ("green-grey", GREEN_GREY)])
def test_key_pairs_do_not_get_worse(t, s, model, name, ab):
    without = pair(None, t, s, model, ab)
    with_ = pair(Profile.default_for(t, s), t, s, model, ab)
    assert with_ > without, (name, without, with_)


# IEC 60445 cable colours (approximate sRGB of real insulation)
IEC = {"braun": (110, 70, 40), "schwarz": (35, 35, 35), "grau": (125, 125, 125), "blau": (40, 80, 170),
       "gruen": (60, 150, 60), "gelb": (220, 200, 40)}


def iec_pairs(prof, t, s, model):
    """Distances of all IEC pairs except green-yellow (stripes of the same PE conductor)."""
    f = _snap(prof)
    names = list(IEC)
    x = seen(f(np.array([IEC[n] for n in names]) / 255.0), t, s, model)
    return {f"{names[i]}-{names[j]}": float(np.linalg.norm(x[i] - x[j]))
            for i in range(len(names)) for j in range(i + 1, len(names)) if {names[i], names[j]} != {"gruen", "gelb"}}


@pytest.mark.parametrize("t,s,model", CASES)
def test_elektro_mode_separates_cable_colours(t, s, model):
    without = iec_pairs(None, t, s, model)
    standard = iec_pairs(Profile.default_for(t, s), t, s, model)
    elektro = iec_pairs(Profile.default_for(t, s, mode="elektro"), t, s, model)
    assert min(elektro.values()) > min(without.values())
    assert min(elektro.values()) >= min(standard.values()) - 1e-3
    brown = lambda d: min(v for k, v in d.items() if "braun" in k)  # noqa: E731
    assert brown(elektro) >= brown(standard)


def test_brown_wire_snaps_only_in_elektro_mode():
    x = np.array(IEC["braun"]) / 255.0
    c0 = lab_to_lch(srgb_to_oklab(x))[1]
    std = lab_to_lch(srgb_to_oklab(snap_srgb(x, Profile.default_for("deutan", 0.6))))[1]
    el = lab_to_lch(srgb_to_oklab(snap_srgb(x, Profile.default_for("deutan", 0.6, mode="elektro"))))[1]
    assert abs(std - c0) < 1e-3  # skin protection keeps brown in the standard mode
    assert el > c0 + 0.01


def test_elektro_mode_switches_skin_protection_off_and_standard_keeps_it():
    assert Profile.default_for("deutan", 0.6).protect_skin is True
    e = Profile.default_for("deutan", 0.6, mode="elektro")
    assert e.protect_skin is False and e.mode == "elektro"
