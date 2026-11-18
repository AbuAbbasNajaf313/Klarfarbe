# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Snap confident colours towards personal, easy-to-tell-apart targets.

Only hue, chroma and (for dark colours) lightness move. Grey, black and
white never change, and colours below the confidence threshold stay as they
are, so the image keeps its natural look and the system never fakes
certainty it does not have.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import categories
from .categories import _hue_diff, _smoothstep, classify, skin_weight
from .oklab import lab_to_lch, lch_to_lab, oklab_to_srgb, srgb_to_oklab
from .profile import Profile


def _targets(profile: Profile) -> np.ndarray:
    """(n_categories, 3) target L_min, chroma, hue for this profile."""
    proto = categories.prototype_lch()
    out = np.zeros_like(proto)
    for i, key in enumerate(categories.KEYS):
        t = profile.targets.get(key)
        hue = proto[i, 2] + np.deg2rad(t.hue_shift_deg if t else 0.0)
        l_min = t.min_lightness if t and t.min_lightness is not None else 0.0
        out[i] = (l_min, proto[i, 1], hue)
    return out


def snap_lab(lab: np.ndarray, profile: Profile) -> tuple[np.ndarray, np.ndarray]:
    """Snap Oklab colours. Returns (new_lab, confidence)."""
    lch = lab_to_lch(lab)
    p, chroma_w = classify(lch)
    idx = p.argmax(axis=-1)
    confidence = p.max(axis=-1) * chroma_w

    tgt = _targets(profile)[idx]  # (..., 3): L_min, C_target, h_target
    alpha = profile.strength * _smoothstep(
        profile.threshold, min(profile.threshold + 0.15, 1.0), confidence
    )
    if profile.protect_skin:
        alpha = alpha * (1.0 - skin_weight(lch))

    L, C, h = lch[..., 0], lch[..., 1], lch[..., 2]
    new_h = h + alpha * _hue_diff(h, tgt[..., 2])
    goal_C = np.minimum(np.maximum(C, tgt[..., 1]), C * profile.max_chroma_gain)
    new_C = C + alpha * (goal_C - C)  # only ever more saturated, and only so much
    new_L = L + alpha * (np.maximum(L, tgt[..., 0]) - L)  # only ever lift dark colours
    return lch_to_lab(np.stack([new_L, new_C, new_h], axis=-1)), confidence


def snap_srgb(rgb: np.ndarray, profile: Profile) -> np.ndarray:
    """sRGB in [0, 1] -> snapped sRGB in [0, 1]."""
    new_lab, _ = snap_lab(srgb_to_oklab(rgb), profile)
    return oklab_to_srgb(new_lab)


def build_lut(profile: Profile, size: int = 33) -> np.ndarray:
    """3D lookup table, shape (size, size, size, 3), indexed [r, g, b]."""
    axis = np.linspace(0.0, 1.0, size)
    r, g, b = np.meshgrid(axis, axis, axis, indexing="ij")
    grid = np.stack([r, g, b], axis=-1)
    return snap_srgb(grid, profile)


def apply_lut(image: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Apply a LUT to a uint8 RGB image (H, W, 3) with trilinear interpolation."""
    n = lut.shape[0]
    x = image.astype(np.float32) * ((n - 1) / 255.0)
    i0 = np.clip(np.floor(x).astype(np.int32), 0, n - 2)
    f = x - i0
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    out = np.zeros(image.shape, dtype=np.float32)
    for dr in (0, 1):
        wr = fr if dr else 1 - fr
        for dg in (0, 1):
            wg = fg if dg else 1 - fg
            for db in (0, 1):
                wb = fb if db else 1 - fb
                out += wr * wg * wb * lut[r0 + dr, g0 + dg, b0 + db]
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


def apply_lut_fast(image: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Nearest-neighbour LUT lookup for live video. Use a LUT of size 64 or more."""
    n = lut.shape[0]
    idx_map = ((np.arange(256, dtype=np.uint32) * (n - 1) + 127) // 255).astype(np.uint32)
    r = idx_map[image[..., 0]]
    g = idx_map[image[..., 1]]
    b = idx_map[image[..., 2]]
    flat_idx = (r * (n * n) + g * n + b).ravel()
    lut_flat = lut.reshape(-1, 3)
    out = np.clip(lut_flat[flat_idx] * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return out.reshape(image.shape)


def write_cube(lut: np.ndarray, path: str | Path, title: str = "Klarfarbe") -> None:
    """Write the LUT as an Adobe/Resolve .cube file (red changes fastest)."""
    n = lut.shape[0]
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                v = lut[r, g, b]
                lines.append(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
