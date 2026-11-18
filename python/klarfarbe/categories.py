# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Colour categories with a confidence value per pixel.

Version 0.1 uses a transparent prototype model in Oklab: chromatic pixels
are compared with category prototypes by hue angle and lightness, so a
muted red is still recognised as "red". Chroma only decides whether a pixel
counts as chromatic at all. A learned colour-naming model can replace
`classify` later without changing the rest of the library.

The confidence values are an unvalidated assignment score, not a calibrated
probability.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .oklab import lab_to_lch, srgb_to_oklab


@dataclass(frozen=True)
class Category:
    key: str
    label_de: str
    prototype_srgb: tuple[int, int, int]
    snaps: bool = True  # False: recognised, but never pulled to its prototype


# Chromatic categories only: grey, black and white are never snapped.
# Turquoise fills the wide gap between green and blue. It does not snap: its
# target is the colour itself, so cyan, teal and petrol are neither pulled
# into green nor into blue.
CATEGORIES: tuple[Category, ...] = (
    Category("red", "Rot", (205, 30, 40)),
    Category("orange", "Orange", (240, 130, 30)),
    Category("yellow", "Gelb", (245, 215, 40)),
    Category("green", "Grün", (40, 155, 60)),
    Category("blue", "Blau", (40, 90, 205)),
    Category("purple", "Lila", (125, 50, 155)),
    Category("pink", "Pink", (235, 125, 180)),
    Category("brown", "Braun", (120, 70, 35)),
    Category("turquoise", "Türkis", (0, 165, 180), snaps=False),
)

KEYS = tuple(c.key for c in CATEGORIES)

# Prototype positions in Oklab LCh, computed once.
_PROTO_LCH = lab_to_lch(
    srgb_to_oklab(np.array([c.prototype_srgb for c in CATEGORIES]) / 255.0)
)

# Model widths: how far (in lightness and hue) a colour may sit from a
# prototype and still belong to it. Tuned by hand for v0.1.
SIGMA_L = 0.16
SIGMA_H = 0.30  # radians, about 17 degrees

# Chroma range in which a pixel fades from "grey" to "chromatic".
ACHROMATIC_LOW = 0.02
ACHROMATIC_HIGH = 0.07
# Near black, sensor noise alone produces chroma of 0.03-0.05 and the hue is
# meaningless. So dark colours need more chroma to count as chromatic (the
# range moves up by up to ACHROMATIC_DARK_EXTRA below L = DARK_RAMP[0]), and
# below DARK_FADE[0] nothing counts as chromatic at all.
ACHROMATIC_DARK_EXTRA = 0.03
DARK_RAMP = (0.15, 0.35)
DARK_FADE = (0.12, 0.26)


def prototype_lch() -> np.ndarray:
    """(n_categories, 3) array of prototype L, C, h."""
    return _PROTO_LCH.copy()


def _smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    if e1 <= e0:  # degenerate range, e.g. threshold = 1.0: hard step
        return (np.asarray(x) >= e0).astype(np.float64)
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _ramp(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    """Linear 0..1 ramp (gentler maximum slope than smoothstep)."""
    if e1 <= e0:
        return (np.asarray(x) >= e0).astype(np.float64)
    return np.clip((np.asarray(x) - e0) / (e1 - e0), 0.0, 1.0)


def _hue_diff(h1: np.ndarray, h2: np.ndarray) -> np.ndarray:
    """Signed shortest angular difference h2 - h1 in (-pi, pi]."""
    d = h2 - h1
    return (d + np.pi) % (2.0 * np.pi) - np.pi


def chromaticity(L: np.ndarray, C: np.ndarray) -> np.ndarray:
    """(...,) in [0, 1]: 0 = grey/black/white or too dark to trust, 1 = clearly coloured."""
    extra = ACHROMATIC_DARK_EXTRA * (1.0 - _smoothstep(DARK_RAMP[0], DARK_RAMP[1], L))
    chroma_w = _ramp(ACHROMATIC_LOW, ACHROMATIC_HIGH, np.asarray(C) - extra)
    return chroma_w * _smoothstep(DARK_FADE[0], DARK_FADE[1], L)


def classify(lch: np.ndarray, proto_lch: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (probabilities, chromaticity).

    probabilities: (..., n_categories), sums to 1 over chromatic categories.
    chromaticity: (...,) in [0, 1], 0 = grey/black/white, 1 = clearly coloured.
    """
    proto = _PROTO_LCH if proto_lch is None else proto_lch
    lch = np.asarray(lch, dtype=np.float64)
    L = lch[..., 0][..., None]
    C = lch[..., 1]
    h = lch[..., 2][..., None]

    dL = (L - proto[:, 0]) / SIGMA_L
    dh = _hue_diff(h, proto[:, 2]) / SIGMA_H
    logits = -0.5 * (dL * dL + dh * dh)
    logits -= logits.max(axis=-1, keepdims=True)
    p = np.exp(logits)
    p /= p.sum(axis=-1, keepdims=True)

    return p, chromaticity(lch[..., 0], C)


# Skin tones of all shades sit in a narrow band: hue around 55 degrees with
# low chroma. Snapping them would make people look orange, so this band is
# protected by default. Brown objects share the band; the profile option
# `protect_skin` can be switched off for tasks such as reading cable colours.
SKIN_HUE = np.deg2rad(55.0)
# core band: typical skin hues, chroma up to about 0.11
SKIN_HUE_INNER = np.deg2rad(20.0)
SKIN_HUE_OUTER = np.deg2rad(30.0)
SKIN_CHROMA_INNER = 0.105
SKIN_CHROMA_OUTER = 0.125
# fringe band: reddish or yellowish skin (e.g. very dark skin around 27 degrees),
# only for low chroma, so muted reds are still snapped
SKIN_FRINGE_HUE = (np.deg2rad(30.0), np.deg2rad(38.0))
SKIN_FRINGE_CHROMA = (0.05, 0.07)


def skin_weight(lch: np.ndarray) -> np.ndarray:
    """(...,) in [0, 1]: 1 = typical skin tone, 0 = clearly not skin."""
    lch = np.asarray(lch, dtype=np.float64)
    dh = np.abs(_hue_diff(lch[..., 2], SKIN_HUE))
    C = lch[..., 1]
    core = (1.0 - _smoothstep(SKIN_HUE_INNER, SKIN_HUE_OUTER, dh)) * (
        1.0 - _smoothstep(SKIN_CHROMA_INNER, SKIN_CHROMA_OUTER, C))
    fringe = (1.0 - _smoothstep(SKIN_FRINGE_HUE[0], SKIN_FRINGE_HUE[1], dh)) * (
        1.0 - _smoothstep(SKIN_FRINGE_CHROMA[0], SKIN_FRINGE_CHROMA[1], C))
    return np.maximum(core, fringe)
