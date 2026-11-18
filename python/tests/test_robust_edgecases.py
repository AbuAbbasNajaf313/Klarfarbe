# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Robustness test: input edge cases (black/white/primaries, out of range, dtype, sizes)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile, apply_lut, build_lut, snap_srgb  # noqa: E402
from klarfarbe.snap import apply_lut_fast  # noqa: E402

DEUTAN = Profile.default_for("deutan", 0.6)
PROTAN = Profile.default_for("protan", 0.9)
PRIMARIES = [(0, 0, 0), (1, 1, 1), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (0, 1, 1), (1, 0, 1)]


@pytest.mark.parametrize("profile", [DEUTAN, PROTAN], ids=["deutan", "protan"])
@pytest.mark.parametrize("c", PRIMARIES)
def test_primaries_finite_and_in_range(profile, c):
    out = snap_srgb(np.array(c, float), profile)
    assert out.shape == (3,)
    assert np.all(np.isfinite(out)) and out.min() >= 0.0 and out.max() <= 1.0


@pytest.mark.parametrize("c", [(0, 0, 0), (1, 1, 1)])
def test_black_and_white_exact(c):
    x = np.array(c, float)
    for p in (DEUTAN, PROTAN):
        assert np.abs(snap_srgb(x, p) - x).max() < 1e-6


def test_out_of_range_floats_give_valid_output():
    x = np.array([[1.5, 0.2, 0.2], [-0.2, 0.5, 0.2], [2.0, 2.0, 2.0], [-1, -1, -1]])
    with np.errstate(invalid="ignore"):  # unused np.where branch on negatives
        out = snap_srgb(x, DEUTAN)
    assert np.all(np.isfinite(out)) and out.min() >= 0.0 and out.max() <= 1.0


def test_nan_pixel_does_not_contaminate_neighbours():
    x = np.array([[np.nan, 0.5, 0.5], [0.6, 0.3, 0.3], [np.inf, 0, 0]])
    with np.errstate(invalid="ignore"):
        out = snap_srgb(x, DEUTAN)
    ref = snap_srgb(x[1], DEUTAN)
    assert np.allclose(out[1], ref)


def test_empty_and_tiny_images():
    lut33, lut64 = build_lut(DEUTAN, 33), build_lut(DEUTAN, 64)
    for shape in [(0, 0, 3), (0, 5, 3), (1, 1, 3), (1, 7, 3)]:
        img = np.full(shape, 128, np.uint8)
        assert apply_lut(img, lut33).shape == shape
        assert apply_lut_fast(img, lut64).shape == shape
    assert snap_srgb(np.zeros((0, 3)), DEUTAN).shape == (0, 3)


def test_extreme_uint8_values_lut():
    img = np.array([[[0, 0, 0], [255, 255, 255], [255, 0, 0], [0, 255, 0], [0, 0, 255]]], np.uint8)
    lut = build_lut(DEUTAN, 33)
    out = apply_lut(img, lut)
    assert out[0, 0].tolist() == [0, 0, 0] and out[0, 1].tolist() == [255, 255, 255]
    direct = np.round(snap_srgb(img / 255.0, DEUTAN) * 255)
    # corners of the cube are LUT nodes: interpolation must hit them exactly
    assert np.abs(out.astype(int) - direct).max() <= 1


def test_large_image_shape_and_dtype():
    img = np.random.default_rng(0).integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    out = apply_lut_fast(img, build_lut(DEUTAN, 64))
    assert out.shape == img.shape and out.dtype == np.uint8


def test_snap_srgb_uint8_input_rejected_or_scaled():
    x8 = np.array([205, 30, 40], dtype=np.uint8)
    try:
        out = snap_srgb(x8, DEUTAN)
    except (TypeError, ValueError):
        return
    assert np.abs(out - snap_srgb(x8 / 255.0, DEUTAN)).max() < 1e-6


def test_apply_lut_float_image_rejected():
    lut = build_lut(DEUTAN, 33)
    with pytest.raises((TypeError, ValueError)):
        apply_lut(np.array([[[0.8, 0.1, 0.1]]]), lut)


def test_build_lut_rejects_size_below_two():
    with pytest.raises(ValueError):
        build_lut(DEUTAN, 1)
