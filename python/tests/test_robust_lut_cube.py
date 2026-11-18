# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Robustness test: LUT accuracy against direct computation, .cube file format."""
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile, apply_lut, build_lut, snap_srgb, write_cube  # noqa: E402
from klarfarbe.oklab import srgb_to_oklab  # noqa: E402
from klarfarbe.snap import apply_lut_fast  # noqa: E402

DEUTAN = Profile.default_for("deutan", 0.6)
PROTAN = Profile.default_for("protan", 0.9)
IMG = np.random.default_rng(7).integers(0, 256, (1, 100000, 3)).astype(np.uint8)


def _de(img, profile, lut, fn):
    direct = snap_srgb(img / 255.0, profile)
    return np.linalg.norm(srgb_to_oklab(fn(img, lut) / 255.0) - srgb_to_oklab(direct), axis=-1)


# measured: n=33 mean 0.0036 / p95 0.016; n=64 mean 0.0018 / p95 0.0063 (Oklab ΔE)
@pytest.mark.parametrize("profile", [DEUTAN, PROTAN], ids=["deutan", "protan"])
@pytest.mark.parametrize("n,mean_max,p95_max", [(33, 0.005, 0.02), (64, 0.0025, 0.009)])
def test_trilinear_lut_error(profile, n, mean_max, p95_max):
    d = _de(IMG, profile, build_lut(profile, n), apply_lut)
    assert d.mean() < mean_max and np.quantile(d, 0.95) < p95_max


def test_nearest_lut64_error():
    d = _de(IMG, DEUTAN, build_lut(DEUTAN, 64), apply_lut_fast)
    assert d.mean() < 0.006 and np.quantile(d, 0.95) < 0.015


def test_lut_nodes_are_exact():
    n = 33
    lut = build_lut(DEUTAN, n)
    # the cube corners are the only nodes that land exactly on uint8 values for n=33
    corners = np.array([[r, g, b] for r in (0, 255) for g in (0, 255) for b in (0, 255)], np.uint8)[None]
    out = apply_lut(corners, lut).astype(int)
    exp = np.round(snap_srgb(corners / 255.0, DEUTAN) * 255).astype(int)
    assert np.abs(out - exp).max() <= 1


def _parse_cube(text):
    lines = text.splitlines()
    header, data = [], []
    for ln in lines:
        if not ln.strip() or ln.startswith("#"):
            continue
        if re.match(r"^[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+$", ln):
            data.append([float(x) for x in ln.split()])
        else:
            assert not data, "keyword after data block"
            header.append(ln)
    return header, np.array(data)


def test_cube_header_and_count(tmp_path):
    n = 17
    p = tmp_path / "k.cube"
    write_cube(build_lut(DEUTAN, n), p)
    raw = p.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw and raw.endswith(b"\n")
    header, data = _parse_cube(p.read_text())
    assert header[0].startswith('TITLE "') and header[0].endswith('"')
    assert f"LUT_3D_SIZE {n}" in header
    assert "DOMAIN_MIN 0.0 0.0 0.0" in header and "DOMAIN_MAX 1.0 1.0 1.0" in header
    assert data.shape == (n ** 3, 3)
    assert data.min() >= 0.0 and data.max() <= 1.0


def test_cube_red_is_fastest_axis(tmp_path):
    n = 5
    ax = np.linspace(0, 1, n)
    ident = np.stack(np.meshgrid(ax, ax, ax, indexing="ij"), -1)  # [r, g, b] -> (r, g, b)
    p = tmp_path / "id.cube"
    write_cube(ident, p)
    _, data = _parse_cube(p.read_text())
    k = np.arange(n ** 3)
    assert np.allclose(data[:, 0], ax[k % n])
    assert np.allclose(data[:, 1], ax[(k // n) % n])
    assert np.allclose(data[:, 2], ax[k // (n * n)])


def test_cube_reload_matches_lut(tmp_path):
    n = 9
    lut = build_lut(PROTAN, n)
    p = tmp_path / "k.cube"
    write_cube(lut, p)
    _, data = _parse_cube(p.read_text())
    back = data.reshape(n, n, n, 3).transpose(2, 1, 0, 3)  # file order b,g,r -> [r,g,b]
    assert np.abs(back - lut).max() < 1e-6


def test_cube_title_is_sanitised(tmp_path):
    p = tmp_path / "t.cube"
    write_cube(build_lut(DEUTAN, 2), p, title='Mein "Profil"\nLUT_3D_SIZE 99')
    header, _ = _parse_cube(p.read_text())
    assert sum(h.startswith("LUT_3D_SIZE") for h in header) == 1
    assert header[0].count('"') == 2
