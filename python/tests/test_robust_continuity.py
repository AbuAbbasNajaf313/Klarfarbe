# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Robustness test: continuity (no jumps/banding), idempotence, grey, skin, spec rules."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile, apply_lut, build_lut, snap_srgb  # noqa: E402
from klarfarbe.categories import skin_weight  # noqa: E402
from klarfarbe.oklab import lab_to_lch, lch_to_lab, oklab_to_srgb, srgb_to_oklab  # noqa: E402

DEUTAN = Profile.default_for("deutan", 0.6)
PROTAN = Profile.default_for("protan", 0.9)


def _with(profile, **kw):
    d = dict(profile.__dict__)
    d.update(kw)
    return Profile(**d)


def ok(x):
    return srgb_to_oklab(np.asarray(x, float))


def de(a, b):
    return np.linalg.norm(ok(a) - ok(b), axis=-1)


# ---------- grey ----------

@pytest.mark.parametrize("profile", [DEUTAN, PROTAN, _with(DEUTAN, threshold=0.2, protect_skin=False)])
def test_full_grey_ramp_unchanged_direct(profile):
    g = np.arange(256) / 255.0
    G = np.stack([g, g, g], -1)
    assert np.abs(snap_srgb(G, profile) - G).max() < 1e-6


def test_grey_ramp_through_lut33_default():
    g = np.arange(256, dtype=np.uint8)
    img = np.stack([g, g, g], -1)[None]
    out = apply_lut(img, build_lut(DEUTAN, 33))[0].astype(int)
    assert (out.max(-1) - out.min(-1)).max() <= 1
    assert np.abs(out - g[:, None]).max() <= 1


def test_grey_ramp_through_lut33_low_threshold():
    g = np.arange(256, dtype=np.uint8)
    img = np.stack([g, g, g], -1)[None]
    out = apply_lut(img, build_lut(_with(PROTAN, threshold=0.2), 33))[0].astype(int)
    assert np.abs(out - g[:, None]).max() <= 3


# ---------- continuity ----------

def test_one_lsb_step_never_jumps_dark():
    a = np.array([19, 1, 12]) / 255.0
    b = np.array([19, 2, 12]) / 255.0
    assert de(snap_srgb(a, DEUTAN), snap_srgb(b, DEUTAN)) < 0.05


def test_one_lsb_steps_random_cube():
    rng = np.random.default_rng(1)
    X = rng.integers(0, 255, (100000, 3))
    worst = 0.0
    for ax in range(3):
        Y = X.copy()
        Y[:, ax] += 1
        worst = max(worst, de(snap_srgb(X / 255, DEUTAN), snap_srgb(Y / 255, DEUTAN)).max())
    assert worst < 0.05


def _hue_sweep_out(profile, lo, hi, step=0.05, L=0.7, C=0.12):
    hs = np.radians(np.arange(lo, hi, step))
    lab = lch_to_lab(np.stack([np.full_like(hs, L), np.full_like(hs, C), hs], -1))
    rgb = oklab_to_srgb(lab)
    return lab_to_lch(ok(snap_srgb(rgb, profile)))[:, 2]


def test_green_blue_boundary_no_hue_jump_default_threshold():
    out = np.degrees(_hue_sweep_out(DEUTAN, 203.0, 209.0)) % 360
    assert out.max() - out.min() < 30.0


def test_cyan_not_pulled_far_into_green():
    lab = lch_to_lab(np.array([0.7, 0.12, np.radians(190.0)]))
    rgb = oklab_to_srgb(lab)
    h_in = np.degrees(lab_to_lch(ok(rgb))[2])
    h_out = np.degrees(lab_to_lch(ok(snap_srgb(rgb, DEUTAN)))[2])
    assert abs(h_out - h_in) < 15.0


def test_moderate_hue_sweep_continuous_near_prototypes():
    # inside the red..yellow range the default threshold keeps transitions smooth
    out = _hue_sweep_out(DEUTAN, 20.0, 110.0, step=0.05)
    steps = np.degrees(np.abs((np.diff(out) + np.pi) % (2 * np.pi) - np.pi))
    assert steps.max() < 2.0


# ---------- idempotence ----------

def test_second_application_moves_less_than_first():
    X = np.random.default_rng(0).random((20000, 3))
    Y = snap_srgb(X, DEUTAN)
    Z = snap_srgb(Y, DEUTAN)
    first, second = de(X, Y), de(Y, Z)
    assert second.mean() < 0.5 * first.mean()
    # Not idempotent by design (dark, weakly coloured pixels gain confidence
    # in the first pass); README warns against chaining two Klarfarbe LUTs.
    # v0.2 measured p99 0.108 (deutan 0.6).
    assert np.quantile(second, 0.99) < 0.12


def test_snap_keeps_category_of_confident_colours():
    """Colours that clearly belong to a category keep it after snapping.

    Exception by design: for deutan the green target is turned past the deutan
    neutral hue towards blue-green, so green may become turquoise. Colours on a
    category border may flip; with blended targets that is not a jump.
    """
    from klarfarbe.categories import KEYS, classify
    X = np.random.default_rng(3).random((20000, 3))
    for prof in (DEUTAN, PROTAN):
        p1, _ = classify(lab_to_lch(ok(X)))
        p2, _ = classify(lab_to_lch(ok(snap_srgb(X, prof))))
        a, b = p1.argmax(-1), p2.argmax(-1)
        intended = (a == KEYS.index("green")) & (b == KEYS.index("turquoise"))
        changed = (a != b) & (p1.max(-1) > 0.8) & ~intended
        assert changed.mean() < 0.005


# ---------- spec rule: saturation and lightness only increase ----------

def test_lightness_never_decreases_and_chroma_only_at_gamut_edge():
    """Spec rule: L only increases; C only increases, except where sRGB cannot
    show the original chroma at the new hue (then C goes exactly to the edge,
    at constant L and hue, instead of per-channel clipping)."""
    from klarfarbe.oklab import max_chroma
    X = np.random.default_rng(5).integers(0, 256, (50000, 3)) / 255
    for prof in (DEUTAN, PROTAN):
        a = lab_to_lch(ok(X))
        b = lab_to_lch(ok(snap_srgb(X, prof)))
        assert (b[:, 0] - a[:, 0]).min() > -1e-4
        edge = max_chroma(b[:, 0], b[:, 2])
        assert (b[:, 1] - np.minimum(a[:, 1], edge)).min() > -1e-4


def test_no_hue_error_from_clipping():
    from klarfarbe.snap import snap_lab
    X = np.random.default_rng(6).integers(0, 256, (50000, 3)) / 255
    lab, _ = snap_lab(ok(X), PROTAN)
    want = lab_to_lch(lab)
    got = lab_to_lch(ok(oklab_to_srgb(lab)))
    m = want[:, 1] > 0.02
    dh = np.degrees(np.abs((got[m, 2] - want[m, 2] + np.pi) % (2 * np.pi) - np.pi))
    assert dh.max() < 0.5


# ---------- skin tones ----------

def _hex(s):
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


# Monk Skin Tone scale (Google, 10 tones, published hex values)
MONK = ["f6ede4", "f3e7db", "f7ead0", "eadaba", "d7bd96", "a07e56", "825c43", "604134", "3a312a", "292420"]
# Fitzpatrick I-VI, approximate sRGB swatches as used in dermatology charts
FITZ = {"I": (244, 208, 177), "II": (231, 180, 143), "III": (210, 158, 124),
        "IV": (186, 119, 80), "V": (165, 93, 43), "VI": (60, 32, 29)}


@pytest.mark.parametrize("profile", [DEUTAN, PROTAN], ids=["deutan", "protan"])
@pytest.mark.parametrize("tone", MONK + list(FITZ.values()))
def test_skin_tones_protected_default(profile, tone):
    x = np.array(_hex(tone) if isinstance(tone, str) else tone) / 255
    assert de(x, snap_srgb(x, profile)) < 0.01


@pytest.mark.parametrize("tone", [FITZ["IV"], FITZ["VI"]], ids=["IV", "VI"])
def test_skin_tones_protected_low_threshold(tone):
    x = np.array(tone) / 255
    assert de(x, snap_srgb(x, _with(DEUTAN, threshold=0.2))) < 0.01


def test_skin_weight_shading_series():
    # the same skin tone in shadow and highlight stays inside the protected band
    base = ok(np.array([190, 140, 110]) / 255)
    for k in (0.6, 0.8, 1.0, 1.15):
        lab = base * np.array([k, 1, 1])
        assert skin_weight(lab_to_lch(lab)) > 0.9
