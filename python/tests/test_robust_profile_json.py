# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Robustness test: profile JSON roundtrip and validation of broken profiles."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile, Target  # noqa: E402
from klarfarbe.categories import KEYS  # noqa: E402

BASE = Profile.default_for("deutan", 0.6).to_dict()


def _mod(fn):
    d = json.loads(json.dumps(BASE))
    fn(d)
    return d


def _random_profiles(n=25, seed=0):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        yield Profile(
            type=str(rng.choice(["protan", "deutan", "unknown"])), severity=float(rng.random()),
            threshold=float(rng.random()), strength=float(rng.random()), protect_skin=bool(rng.random() < 0.5),
            max_chroma_gain=float(1 + 3 * rng.random()),
            targets={k: Target(float(rng.normal(0, 20)), None if rng.random() < 0.5 else float(rng.random()))
                     for k in KEYS if rng.random() < 0.5})


def test_roundtrip_random_profiles(tmp_path):
    for i, p in enumerate(_random_profiles()):
        path = tmp_path / f"{i}.json"
        p.save(path)
        assert Profile.load(path).to_dict() == p.to_dict()
        json.loads(path.read_text(), parse_constant=lambda c: pytest.fail(f"non-standard JSON {c}"))


@pytest.mark.parametrize("t", ["protan", "deutan", "unknown"])
@pytest.mark.parametrize("s", [0.0, 0.5, 1.0])
def test_default_profiles_roundtrip(t, s):
    p = Profile.default_for(t, s)
    assert Profile.from_dict(json.loads(json.dumps(p.to_dict()))).to_dict() == p.to_dict()


def test_unknown_top_level_field_ignored():
    assert Profile.from_dict(_mod(lambda d: d.__setitem__("future_field", {"x": 1}))).type == "deutan"


@pytest.mark.parametrize("bad", [
    lambda d: d.__setitem__("format", "other"),
    lambda d: d.pop("format"),
    lambda d: d.__setitem__("type", "tritan"),
    lambda d: d.__setitem__("severity", 1.5),
    lambda d: d.__setitem__("severity", float("nan")),
    lambda d: d.__setitem__("threshold", -0.1),
    lambda d: d.__setitem__("strength", 2),
    lambda d: d.__setitem__("max_chroma_gain", 0.5),
], ids=["format", "noformat", "tritan", "sev>1", "sevNaN", "thr<0", "strength>1", "gain<1"])
def test_invalid_values_raise_valueerror(bad):
    with pytest.raises(ValueError):
        Profile.from_dict(_mod(bad))


def test_unknown_field_inside_target_ignored():
    d = _mod(lambda d: d["targets"]["green"].__setitem__("axis_error", 0.3))
    assert Profile.from_dict(d).targets["green"].hue_shift_deg == BASE["targets"]["green"]["hue_shift_deg"]


def test_protect_skin_string_rejected():
    with pytest.raises(ValueError):
        Profile.from_dict(_mod(lambda d: d.__setitem__("protect_skin", "false")))


def test_max_chroma_gain_nan_rejected():
    with pytest.raises(ValueError):
        Profile.from_dict(_mod(lambda d: d.__setitem__("max_chroma_gain", float("nan"))))


@pytest.mark.parametrize("v", [5.0, -1.0, float("nan")])
def test_min_lightness_out_of_range_rejected(v):
    with pytest.raises(ValueError):
        Profile.from_dict(_mod(lambda d: d["targets"]["red"].__setitem__("min_lightness", v)))


@pytest.mark.parametrize("v", ["20", float("nan")])
def test_hue_shift_type_checked_at_load(v):
    with pytest.raises(ValueError):
        Profile.from_dict(_mod(lambda d: d["targets"]["green"].__setitem__("hue_shift_deg", v)))


def test_unknown_category_rejected_or_dropped():
    try:
        p = Profile.from_dict(_mod(lambda d: d["targets"].__setitem__("cyan", {"hue_shift_deg": 10})))
    except ValueError:
        return
    assert "cyan" not in p.targets


@pytest.mark.parametrize("data", [
    _mod(lambda d: d.pop("type")), _mod(lambda d: d.pop("severity")),
    _mod(lambda d: d.__setitem__("targets", [])), _mod(lambda d: d["targets"].__setitem__("green", 5)),
    [1, 2, 3],
], ids=["no-type", "no-severity", "targets-list", "target-int", "list"])
def test_structural_errors_raise_valueerror(data):
    with pytest.raises(ValueError):
        Profile.from_dict(data)


def test_save_never_writes_nan(tmp_path):
    p = Profile.default_for("protan", 0.9)
    p.targets["green"].hue_shift_deg = math.nan
    try:
        p.save(tmp_path / "x.json")
    except ValueError:
        return
    text = (tmp_path / "x.json").read_text()
    assert "NaN" not in text
