# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile, apply_lut, build_lut, snap_srgb, write_cube  # noqa: E402
from klarfarbe.categories import KEYS, classify  # noqa: E402
from klarfarbe.oklab import lab_to_lch, oklab_to_srgb, srgb_to_linear, srgb_to_oklab  # noqa: E402
from klarfarbe.snap import apply_lut_fast  # noqa: E402

DEUTAN = Profile.default_for("deutan", 0.6)


def rgb(*c):
    return np.array(c, dtype=np.float64) / 255.0


def category(*c):
    p, _ = classify(lab_to_lch(srgb_to_oklab(rgb(*c))))
    return KEYS[int(p.argmax())]


def chroma(x):
    return float(lab_to_lch(srgb_to_oklab(x))[1])


def test_oklab_roundtrip():
    colours = np.random.default_rng(0).random((500, 3))
    back = oklab_to_srgb(srgb_to_oklab(colours))
    # The published matrices are rounded to 10 digits; 1e-5 is far below 1/255.
    assert np.abs(back - colours).max() < 1e-5


@pytest.mark.parametrize(
    "colour,expected",
    [((160, 80, 75), "red"), ((70, 120, 70), "green"), ((55, 30, 60), "purple"),
     ((230, 210, 80), "yellow"), ((120, 170, 220), "blue"), ((110, 75, 50), "brown")],
)
def test_categories(colour, expected):
    assert category(*colour) == expected


@pytest.mark.parametrize("grey", [(0, 0, 0), (128, 128, 128), (255, 255, 255), (40, 40, 40)])
def test_grey_black_white_never_change(grey):
    x = rgb(*grey)
    assert np.abs(snap_srgb(x, DEUTAN) - x).max() < 1e-6


def test_muted_red_becomes_more_saturated():
    x = rgb(160, 80, 75)
    assert chroma(snap_srgb(x, DEUTAN)) > chroma(x) * 1.5


def test_dark_purple_is_lifted():
    x = rgb(55, 30, 60)  # aubergine
    L_before = float(srgb_to_oklab(x)[0])
    L_after = float(srgb_to_oklab(snap_srgb(x, DEUTAN))[0])
    assert L_after > L_before + 0.1


@pytest.mark.parametrize("skin", [(225, 180, 150), (190, 140, 110), (120, 85, 65)])
def test_skin_tones_protected_by_default(skin):
    x = rgb(*skin)
    assert np.abs(snap_srgb(x, DEUTAN) - x).max() < 2 / 255


def test_handwerk_mode_snaps_brown():
    work = Profile.default_for("deutan", 0.6)
    work.protect_skin = False
    x = rgb(110, 75, 50)
    assert chroma(snap_srgb(x, work)) > chroma(x)


def test_chroma_gain_is_capped():
    x = rgb(160, 80, 75)
    assert chroma(snap_srgb(x, DEUTAN)) <= chroma(x) * DEUTAN.max_chroma_gain + 1e-6


def test_profile_roundtrip(tmp_path):
    path = tmp_path / "p.json"
    DEUTAN.save(path)
    data = json.loads(path.read_text())
    assert data["format"] == "klarfarbe-profile" and data["version"] == "0.1"
    assert Profile.load(path).to_dict() == DEUTAN.to_dict()


def test_invalid_profile_rejected():
    with pytest.raises(ValueError):
        Profile(type="tritan")
    with pytest.raises(ValueError):
        Profile(threshold=1.5)


def test_threshold_one_does_not_crash():
    strict = Profile.default_for("deutan", 0.6)
    strict.threshold = 1.0
    out = snap_srgb(rgb(160, 80, 75), strict)
    assert np.all(np.isfinite(out))


def test_lut_matches_direct_snap():
    lut = build_lut(DEUTAN, 33)
    img = (np.random.default_rng(1).random((20, 20, 3)) * 255).astype(np.uint8)
    direct = (snap_srgb(img / 255.0, DEUTAN) * 255).round()
    assert np.abs(apply_lut(img, lut).astype(float) - direct).mean() < 3.0
    assert apply_lut_fast(img, build_lut(DEUTAN, 64)).shape == img.shape


def test_cube_file(tmp_path):
    path = tmp_path / "k.cube"
    write_cube(build_lut(DEUTAN, 9), path)
    lines = path.read_text().splitlines()
    assert "LUT_3D_SIZE 9" in lines
    assert len([l for l in lines if l[0].isdigit()]) == 9 ** 3
def test_forward_compatibility():
    data = {
        "format": "klarfarbe-profile",
        "version": "9.9",
        "type": "deutan",
        "severity": 0.6,
        "future_field": "ignore_me",
        "targets": {
            "green": {"hue_shift_deg": 15.0, "future_target_attr": 123}
        }
    }
    p = Profile.from_dict(data)
    assert p.type == "deutan"
    assert p.severity == 0.6
    assert p.targets["green"].hue_shift_deg == 15.0


def test_negative_or_out_of_bounds_srgb_safe():
    noisy_srgb = np.array([-0.5, 1.5, 0.2])
    linear = srgb_to_linear(noisy_srgb)
    assert np.all(np.isfinite(linear))
    assert linear[0] == 0.0
    assert linear[1] == 1.0
