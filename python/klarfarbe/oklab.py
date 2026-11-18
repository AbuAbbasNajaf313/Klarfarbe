# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""sRGB <-> Oklab conversion, vectorised with NumPy.

Matrices from Björn Ottosson's reference implementation:
https://bottosson.github.io/posts/oklab/

All functions accept arrays of shape (..., 3) and return the same shape.
sRGB values are floats in [0, 1].
"""
from __future__ import annotations

import numpy as np

_RGB_TO_LMS = np.array(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ]
)
_LMS_TO_LAB = np.array(
    [
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ]
)
_LAB_TO_LMS = np.array(
    [
        [1.0, 0.3963377774, 0.2158037573],
        [1.0, -0.1055613458, -0.0638541728],
        [1.0, -0.0894841775, -1.2914855480],
    ]
)
_LMS_TO_RGB = np.array(
    [
        [4.0767416621, -3.3077115913, 0.2309699292],
        [-1.2684380046, 2.6097574011, -0.3413193965],
        [-0.0041960863, -0.7034186147, 1.7076147010],
    ]
)


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    """sRGB -> linear; inputs are clipped to [0, 1] (no NaN for negatives)."""
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1.0 / 2.4) - 0.055)


def srgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    """sRGB in [0, 1] -> Oklab (L, a, b)."""
    lin = srgb_to_linear(rgb)
    lms = lin @ _RGB_TO_LMS.T
    return np.cbrt(lms) @ _LMS_TO_LAB.T


def oklab_to_srgb(lab: np.ndarray) -> np.ndarray:
    """Oklab (L, a, b) -> sRGB in [0, 1], clipped to the gamut."""
    lms_ = np.asarray(lab, dtype=np.float64) @ _LAB_TO_LMS.T
    lin = (lms_ ** 3) @ _LMS_TO_RGB.T
    return linear_to_srgb(lin)


def lab_to_lch(lab: np.ndarray) -> np.ndarray:
    """Oklab -> (L, chroma, hue in radians)."""
    lab = np.asarray(lab, dtype=np.float64)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    return np.stack([L, np.hypot(a, b), np.arctan2(b, a)], axis=-1)


def lch_to_lab(lch: np.ndarray) -> np.ndarray:
    lch = np.asarray(lch, dtype=np.float64)
    L, C, h = lch[..., 0], lch[..., 1], lch[..., 2]
    return np.stack([L, C * np.cos(h), C * np.sin(h)], axis=-1)


# ---------- gamut ----------

# Linear sRGB of an Oklab LCh colour is a cubic in C for fixed L and h:
# lms_j = L + C * u_j(h), lin_i = sum_j M_ij * lms_j**3.
_U_COS = _LAB_TO_LMS[:, 1]
_U_SIN = _LAB_TO_LMS[:, 2]
GAMUT_BISECT_STEPS = 18
GAMUT_NEWTON_STEPS = 3
GAMUT_C_HI = 0.5  # above every sRGB chroma (max is about 0.32)


def _lin_rgb_lch(L: np.ndarray, C: np.ndarray, u: np.ndarray) -> np.ndarray:
    lms_ = L[..., None] + C[..., None] * u  # (..., 3)
    return (lms_ ** 3) @ _LMS_TO_RGB.T


def max_chroma(L: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Largest Oklab chroma that is still inside sRGB at lightness L and hue h.

    Bisection on "all channels in [0, 1]", then three Newton steps on the
    channel that limits the gamut, so the result is exact to rounding and
    independent of small differences in the bisection (Python/JS parity).
    Returns 0 where even the grey L is outside [0, 1].
    """
    L = np.asarray(L, dtype=np.float64)
    h = np.asarray(h, dtype=np.float64)
    L, h = np.broadcast_arrays(L, h)
    u = np.cos(h)[..., None] * _U_COS + np.sin(h)[..., None] * _U_SIN
    lo = np.zeros(L.shape)
    hi = np.full(L.shape, GAMUT_C_HI)
    for _ in range(GAMUT_BISECT_STEPS):
        mid = 0.5 * (lo + hi)
        rgb = _lin_rgb_lch(L, mid, u)
        inside = (rgb.min(axis=-1) >= 0.0) & (rgb.max(axis=-1) <= 1.0)
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    # the channel and bound that are violated at hi limit the gamut
    rgb = _lin_rgb_lch(L, hi, u)
    viol = np.maximum(rgb - 1.0, -rgb)
    ch = viol.argmax(axis=-1)
    bound = np.where(np.take_along_axis(rgb, ch[..., None], -1)[..., 0] > 0.5, 1.0, 0.0)
    row = _LMS_TO_RGB[ch]  # (..., 3)
    c = hi
    for _ in range(GAMUT_NEWTON_STEPS):
        lms_ = L[..., None] + c[..., None] * u
        f = np.sum(row * lms_ ** 3, axis=-1) - bound
        df = np.sum(row * 3.0 * lms_ ** 2 * u, axis=-1)
        step = np.where(np.abs(df) > 1e-12, f / np.where(np.abs(df) > 1e-12, df, 1.0), 0.0)
        c = c - step
    # keep Newton inside the bisection bracket (it only refines)
    c = np.clip(c, lo, hi)
    grey_ok = (L >= 0.0) & (L <= 1.0)
    return np.where(grey_ok & (lo > 0.0), c, np.where(grey_ok, lo, 0.0))
