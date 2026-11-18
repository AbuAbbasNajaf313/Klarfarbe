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
from .categories import _hue_diff, _ramp, _smoothstep, classify, skin_weight
from .oklab import lab_to_lch, lch_to_lab, max_chroma, oklab_to_srgb, srgb_to_oklab
from .profile import Profile


# Default LUT size (Python and JS). 64 = power of two as needed by the
# OpenXR passthrough colour LUT; trilinear error about half of 33.
LUT_N = 64

# Confidence window: snapping fades in between threshold and threshold + this.
# Wide on purpose, so that small input changes give small output changes.
CONFIDENCE_WINDOW = 0.30
# Lightness is lifted by at most this much, so dark noise is not amplified.
MAX_LIFT = 0.21
# ... and the lift fades in between these lightness values.
LIFT_FADE = (0.12, 0.30)
# A colour this many hue sigmas away from a prototype gets no confidence from it.
PROXIMITY = (1.5, 3.0)
# Over-exposed pixels (a channel near 255) carry no reliable hue: fade out.
CLIP_FADE = (0.90, 0.995)
# Snapped colours keep this distance to the edge of the sRGB gamut.
GAMUT_HEADROOM = 0.92


def _targets(profile: Profile) -> np.ndarray:
    """(n_categories, 5): L_min, target chroma, target hue, hue shift, pull (1/0)."""
    proto = categories.prototype_lch()
    out = np.zeros((len(proto), 5))
    for i, cat in enumerate(categories.CATEGORIES):
        t = profile.targets.get(cat.key)
        shift = np.deg2rad(t.hue_shift_deg if t else 0.0)
        l_min = t.min_lightness if t and t.min_lightness is not None else 0.0
        if t and t.min_chroma is not None:
            c_t = t.min_chroma
        else:
            c_t = proto[i, 1] if cat.snaps else 0.0
        out[i] = (l_min, c_t, proto[i, 2] + shift, shift, 1.0 if cat.snaps else 0.0)
    return out


def _max_channel(lab: np.ndarray) -> np.ndarray:
    return oklab_to_srgb(lab).max(axis=-1)


def snap_lab(lab: np.ndarray, profile: Profile) -> tuple[np.ndarray, np.ndarray]:
    """Snap Oklab colours. Returns (new_lab, confidence).

    The target is not the single most likely category but the
    probability-weighted mix of all category targets (hue averaged on the
    circle around the input hue), so the output changes smoothly with the
    input.
    """
    lab = np.asarray(lab, dtype=np.float64)
    lch = lab_to_lch(lab)
    L, C, h = lch[..., 0], lch[..., 1], lch[..., 2]
    p, chroma_w = classify(lch)
    proto = categories.prototype_lch()
    tg = _targets(profile)

    # confidence (unvalidated score, not a probability): chromatic, not too
    # dark, near a prototype hue (not between two far-apart ones), not
    # over-exposed. Ambiguity between neighbouring categories is handled by
    # the blended target below, not by the confidence.
    dh_proto = np.abs(_hue_diff(h[..., None], proto[:, 2])) / categories.SIGMA_H
    near = np.sum(p * (1.0 - _ramp(PROXIMITY[0], PROXIMITY[1], dh_proto)), axis=-1)
    clip_w = 1.0
    if profile.clip_guard:
        clip_w = 1.0 - _ramp(CLIP_FADE[0], CLIP_FADE[1], _max_channel(lab))
    confidence = chroma_w * near * clip_w

    alpha = profile.strength * _ramp(
        profile.threshold, min(profile.threshold + CONFIDENCE_WINDOW, 1.0), confidence
    )
    if profile.protect_skin:
        alpha = alpha * (1.0 - skin_weight(lch))

    # probability-weighted targets
    pull = tg[:, 4]
    d_hue = pull * _hue_diff(h[..., None], tg[:, 2]) + (1.0 - pull) * tg[:, 3]
    goal_h = h + np.sum(p * d_hue, axis=-1)
    goal_C = np.sum(p * np.minimum(np.maximum(C[..., None], tg[:, 1]), C[..., None] * profile.max_chroma_gain),
                    axis=-1)
    lift = np.sum(p * np.minimum(np.maximum(tg[:, 0] - L[..., None], 0.0), MAX_LIFT), axis=-1)
    lift = lift * _smoothstep(LIFT_FADE[0], LIFT_FADE[1], L)  # hue of very dark colours is mostly noise

    new_L = L + alpha * lift  # only ever lift
    new_h = h + alpha * (goal_h - h)
    c_max = max_chroma(new_L, new_h)
    goal_C = np.maximum(np.minimum(goal_C, GAMUT_HEADROOM * c_max), C)  # never less saturated
    new_C = C + alpha * (goal_C - C)
    # gamut mapping at constant L and h instead of per-channel clipping
    new_C = np.where(alpha > 0.0, np.minimum(new_C, c_max), C)
    return lch_to_lab(np.stack([new_L, new_C, new_h], axis=-1)), confidence


def _as_unit_float(rgb) -> np.ndarray:
    """sRGB input as float64 in [0, 1]. uint8/uint16 are scaled, NaN becomes 0."""
    arr = np.asarray(rgb)
    if arr.dtype == np.uint8:
        arr = arr.astype(np.float64) / 255.0
    elif arr.dtype == np.uint16:
        arr = arr.astype(np.float64) / 65535.0
    elif arr.dtype.kind in "biu":
        raise TypeError(f"sRGB input must be float in [0, 1], uint8 or uint16, got {arr.dtype}")
    elif arr.dtype.kind != "f":
        raise TypeError(f"sRGB input must be numeric, got {arr.dtype}")
    if arr.shape[-1:] != (3,):
        raise ValueError(f"sRGB input must have shape (..., 3), got {arr.shape}")
    arr = np.nan_to_num(arr.astype(np.float64), nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(arr, 0.0, 1.0)


def snap_srgb(rgb: np.ndarray, profile: Profile) -> np.ndarray:
    """sRGB in [0, 1] (float) or uint8/uint16 -> snapped sRGB float in [0, 1].

    Values outside [0, 1] are clipped, NaN counts as 0.
    """
    new_lab, _ = snap_lab(srgb_to_oklab(_as_unit_float(rgb)), profile)
    return oklab_to_srgb(new_lab)


def build_lut(profile: Profile, size: int = LUT_N) -> np.ndarray:
    """3D lookup table, shape (size, size, size, 3), indexed [r, g, b].

    size must be 2..256 (.cube limit). 64 is the default: it matches the
    Meta passthrough colour LUT and keeps the interpolation error small.
    """
    if isinstance(size, bool) or not isinstance(size, (int, np.integer)) or not 2 <= size <= 256:
        raise ValueError(f"LUT size must be an integer in [2, 256], got {size!r}")
    axis = np.linspace(0.0, 1.0, int(size))
    r, g, b = np.meshgrid(axis, axis, axis, indexing="ij")
    grid = np.stack([r, g, b], axis=-1)
    return snap_srgb(grid, profile)


def _check_lut_input(image: np.ndarray, lut: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(image)
    if image.dtype != np.uint8:
        raise TypeError(f"image must be uint8 RGB, got {image.dtype}; for float images use snap_srgb")
    if image.shape[-1:] != (3,):
        raise ValueError(f"image must have shape (..., 3), got {image.shape}")
    lut = np.asarray(lut)
    if lut.ndim != 4 or lut.shape[3] != 3 or not (lut.shape[0] == lut.shape[1] == lut.shape[2] >= 2):
        raise ValueError(f"lut must have shape (n, n, n, 3) with n >= 2, got {lut.shape}")
    return image, lut


# Pixels per block in apply_lut: bounds the temporary memory (about 100 MB)
# independent of the image size.
APPLY_BLOCK = 1 << 20


def apply_lut(image: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Apply a LUT to a uint8 RGB image (..., 3) with trilinear interpolation.

    Works in blocks of APPLY_BLOCK pixels and in float32, so a 12-MP photo
    does not need gigabytes of temporary memory.
    """
    image, lut = _check_lut_input(image, lut)
    n = lut.shape[0]
    lut32 = lut.astype(np.float32, copy=False)
    flat = image.reshape(-1, 3)
    out = np.empty(flat.shape, dtype=np.uint8)
    scale = np.float32((n - 1) / 255.0)
    for start in range(0, len(flat), APPLY_BLOCK):
        block = flat[start:start + APPLY_BLOCK]
        x = block.astype(np.float32) * scale
        i0 = np.clip(np.floor(x).astype(np.int32), 0, n - 2)
        f = x - i0
        r0, g0, b0 = i0[:, 0], i0[:, 1], i0[:, 2]
        fr, fg, fb = f[:, 0:1], f[:, 1:2], f[:, 2:3]
        acc = np.zeros(block.shape, dtype=np.float32)
        for dr in (0, 1):
            wr = fr if dr else 1 - fr
            for dg in (0, 1):
                wg = fg if dg else 1 - fg
                for db in (0, 1):
                    wb = fb if db else 1 - fb
                    acc += wr * wg * wb * lut32[r0 + dr, g0 + dg, b0 + db]
        out[start:start + APPLY_BLOCK] = np.clip(acc * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return out.reshape(image.shape)


def apply_lut_fast(image: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Nearest-neighbour LUT lookup for live video. Use a LUT of size 64 or more.

    The LUT is converted to uint8 once and looked up through a flat index.
    """
    image, lut = _check_lut_input(image, lut)
    n = lut.shape[0]
    idx_map = ((np.arange(256, dtype=np.uint32) * (n - 1) + 127) // 255).astype(np.uint32)
    lut8 = np.clip(lut.reshape(-1, 3) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    flat_idx = (idx_map[image[..., 0]] * (n * n) + idx_map[image[..., 1]] * n + idx_map[image[..., 2]])
    return lut8[flat_idx.ravel()].reshape(image.shape)


def _cube_title(title: str) -> str:
    lines = str(title).replace('"', "'").splitlines()
    text = lines[0] if lines else ""
    return text.encode("ascii", "replace").decode("ascii")


def write_cube(lut: np.ndarray, path: str | Path, title: str = "Klarfarbe") -> None:
    """Write the LUT as an Adobe/Resolve .cube file (red changes fastest)."""
    n = lut.shape[0]
    lines = [f'TITLE "{_cube_title(title)}"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                v = lut[r, g, b]
                lines.append(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
