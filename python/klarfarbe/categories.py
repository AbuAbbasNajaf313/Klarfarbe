# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Colour categories with a confidence value per pixel.

Version 0.1 uses a transparent prototype model in Oklab: chromatic pixels
are compared with category prototypes by hue angle and lightness, so a
muted red is still recognised as "red". Chroma only decides whether a pixel
counts as chromatic at all. A learned colour-naming model can replace
`classify` later without changing the rest of the library.
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


# Chromatic categories only: grey, black and white are never snapped.
CATEGORIES: tuple[Category, ...] = (
    Category("red", "Rot", (205, 30, 40)),
    Category("orange", "Orange", (240, 130, 30)),
    Category("yellow", "Gelb", (245, 215, 40)),
    Category("green", "Grün", (40, 155, 60)),
    Category("blue", "Blau", (40, 90, 205)),
    Category("purple", "Lila", (125, 50, 155)),
    Category("pink", "Pink", (235, 125, 180)),
    Category("brown", "Braun", (120, 70, 35)),
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
ACHROMATIC_LOW = 0.025
ACHROMATIC_HIGH = 0.06


def prototype_lch() -> np.ndarray:
    """(n_categories, 3) array of prototype L, C, h."""
    return _PROTO_LCH.copy()


def _smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    if e1 <= e0:  # degenerate range, e.g. threshold = 1.0: hard step
        return (np.asarray(x) >= e0).astype(np.float64)
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _hue_diff(h1: np.ndarray, h2: np.ndarray) -> np.ndarray:
    """Signed shortest angular difference h2 - h1 in (-pi, pi]."""
    d = h2 - h1
    return (d + np.pi) % (2.0 * np.pi) - np.pi


def classify(lch: np.ndarray, proto_lch: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (probabilities, chromaticity).

    probabilities: (..., n_categories), sums to 1 over chromatic categories.
    chromaticity: (...,) in [0, 1], 0 = grey/black/white, 1 = clearly coloured.
    The confidence for snapping is probabilities.max(-1) * chromaticity.
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

    chromaticity = _smoothstep(ACHROMATIC_LOW, ACHROMATIC_HIGH, C)
    return p, chromaticity


# Skin tones of all shades sit in a narrow band: hue around 55 degrees with
# low chroma. Snapping them would make people look orange, so this band is
# protected by default. Brown objects share the band; the profile option
# `protect_skin` can be switched off for tasks such as reading cable colours.
SKIN_HUE = np.deg2rad(55.0)
SKIN_HUE_INNER = np.deg2rad(20.0)
SKIN_HUE_OUTER = np.deg2rad(32.0)
SKIN_CHROMA_INNER = 0.085
SKIN_CHROMA_OUTER = 0.105


def skin_weight(lch: np.ndarray) -> np.ndarray:
    """(...,) in [0, 1]: 1 = typical skin tone, 0 = clearly not skin."""
    lch = np.asarray(lch, dtype=np.float64)
    dh = np.abs(_hue_diff(lch[..., 2], SKIN_HUE))
    in_hue = 1.0 - _smoothstep(SKIN_HUE_INNER, SKIN_HUE_OUTER, dh)
    in_chroma = 1.0 - _smoothstep(SKIN_CHROMA_INNER, SKIN_CHROMA_OUTER, lch[..., 1])
    return in_hue * in_chroma
