# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Colour arrangement test (D-15 principle) and its scoring.

The person orders 15 caps by similarity, starting from a fixed reference cap.
Two rounds: saturated caps, then pale (desaturated) caps, which reveal milder
deficiencies. Scoring follows the moment-of-inertia method of Vingrys and
King-Smith (1988): the colour differences between neighbouring caps in the
person's order give a confusion axis (its angle tells protan from deutan)
and a confusion index (1 = perfect order, higher = more crossings).

The caps here are generated in Oklab, not taken from the Munsell D-15, so the
angles of the protan and deutan axes are calibrated by letting simulated
observers (Machado et al. 2009) take the test. See `calibrate()`.

This is a screening aid on an uncalibrated screen, not a medical diagnosis.
"""
from __future__ import annotations

import numpy as np

from .oklab import lch_to_lab, oklab_to_srgb, srgb_to_oklab

N_CAPS = 15
LIGHTNESS = 0.68
CHROMA = {"saturated": 0.10, "pale": 0.05}
START_HUE_DEG = 25.0

# Machado, Oliveira & Fernandes (2009), full-strength simulation matrices
# (linear RGB). Weaker forms are approximated by blending with identity.
_MACHADO = {
    "protan": np.array([[0.152286, 1.052583, -0.204868],
                        [0.114503, 0.786281, 0.099216],
                        [-0.003882, -0.048116, 1.051998]]),
    "deutan": np.array([[0.367322, 0.860646, -0.227968],
                        [0.280085, 0.672501, 0.047413],
                        [-0.011820, 0.042940, 0.968881]]),
}


def caps(round_: str) -> np.ndarray:
    """(N_CAPS + 1, 3) sRGB in [0, 1]; index 0 is the fixed reference cap."""
    hues = np.deg2rad(START_HUE_DEG + np.arange(N_CAPS + 1) * 360.0 / (N_CAPS + 1))
    lch = np.stack([np.full_like(hues, LIGHTNESS), np.full_like(hues, CHROMA[round_]), hues], axis=-1)
    return oklab_to_srgb(lch_to_lab(lch))


def _ab(rgb: np.ndarray) -> np.ndarray:
    return srgb_to_oklab(rgb)[..., 1:]


def moments(order: list[int], cap_rgb: np.ndarray) -> dict:
    """Vingrys & King-Smith moment of inertia for an arrangement.

    order: cap indices 1..N_CAPS in the person's order (reference 0 is prepended).
    Returns angle (degrees, axis in [-90, 90)), major and minor radius.
    """
    seq = [0] + list(order)
    pts = _ab(cap_rgb[seq])
    d = np.diff(pts, axis=0)
    m = d.T @ d  # 2x2 scatter of difference vectors
    vals, vecs = np.linalg.eigh(m)
    major_vec = vecs[:, 1]
    angle = np.degrees(np.arctan2(major_vec[1], major_vec[0]))
    angle = (angle + 90.0) % 180.0 - 90.0
    n = len(d)
    return {
        "angle": float(angle),
        "major": float(np.sqrt(vals[1] / n)),
        "minor": float(np.sqrt(max(vals[0], 0.0) / n)),
    }


def _perfect_major(round_: str) -> float:
    return moments(list(range(1, N_CAPS + 1)), caps(round_))["major"]


def confusion_index(order: list[int], round_: str) -> tuple[float, float]:
    """(confusion index, axis angle). Index 1.0 = perfect order."""
    mo = moments(order, caps(round_))
    return mo["major"] / _perfect_major(round_), mo["angle"]


# ---------- simulated observers for calibration ----------

def simulate(rgb: np.ndarray, type_: str, severity: float) -> np.ndarray:
    from .oklab import linear_to_srgb, srgb_to_linear

    m = (1 - severity) * np.eye(3) + severity * _MACHADO[type_]
    return linear_to_srgb(srgb_to_linear(rgb) @ m.T)


# Simulated observer: told to "order by colour", a person weights lightness
# less than hue; and colours closer than a perceptual threshold blur, which is
# why the pale round catches milder forms. Modelled as a lower lightness
# weight plus Gaussian noise on the perceived colour (Oklab units).
SIM_LIGHTNESS_WEIGHT = 0.3
SIM_NOISE = 0.006


def simulated_order(round_: str, type_: str | None, severity: float,
                    rng: np.random.Generator | None = None) -> list[int]:
    """Greedy arrangement: always pick the remaining cap that looks closest."""
    rgb = caps(round_)
    seen = srgb_to_oklab(simulate(rgb, type_, severity) if type_ else rgb)
    if rng is not None:
        seen = seen + rng.normal(0.0, SIM_NOISE, seen.shape)
    w = np.array([SIM_LIGHTNESS_WEIGHT, 1.0, 1.0])
    order, last, left = [], 0, set(range(1, N_CAPS + 1))
    while left:
        nxt = min(left, key=lambda i: (float(np.sum(((seen[i] - seen[last]) * w) ** 2)), i))
        order.append(nxt)
        left.remove(nxt)
        last = nxt
    return order


def calibrate(trials: int = 40, seed: int = 0) -> dict:
    """Failure rate and median axis angle per type, severity and round."""
    rng = np.random.default_rng(seed)
    out = {}
    for t in ("protan", "deutan"):
        rows = []
        for s in np.round(np.arange(0.3, 1.01, 0.1), 2):
            row = {"severity": float(s)}
            for r in CHROMA:
                res = [confusion_index(simulated_order(r, t, float(s), rng), r) for _ in range(trials)]
                ci = np.array([c for c, _ in res])
                ang = np.array([a for c, a in res if c > FAIL_INDEX])
                row[r] = {"fail_rate": float((ci > FAIL_INDEX).mean()),
                          "angle": float(np.median(ang)) if len(ang) else None}
            rows.append(row)
        out[t] = rows
    return out


# Calibrated with calibrate() (40 trials per cell). Protan axes fell between
# +5 and +13 degrees, deutan axes between -4 and +5 degrees in Oklab a/b.
# Angles closer than TYPE_MARGIN to both are reported as uncertain.
FAIL_INDEX = 1.6
AXIS_ANGLE = {"protan": 9.0, "deutan": -3.0}
TYPE_MARGIN = 3.0


def evaluate(order_saturated: list[int], order_pale: list[int]) -> dict:
    """Turn two arrangements into a profile suggestion.

    Severity is coarse on purpose: failing the saturated round means strong,
    failing only the pale round means moderate, passing both means mild or none.
    """
    ci_s, ang_s = confusion_index(order_saturated, "saturated")
    ci_p, ang_p = confusion_index(order_pale, "pale")
    fail_s, fail_p = ci_s > FAIL_INDEX, ci_p > FAIL_INDEX
    base = {"index_saturated": ci_s, "index_pale": ci_p}
    if fail_s:
        severity, angle = 0.85, ang_s
    elif fail_p:
        # In calibration, about one in five moderate cases showed its axis on
        # the wrong side, so the pale round only measures severity.
        return {**base, "type": "unknown", "severity": 0.6, "angle": ang_p,
                "note": "Mittlere Rot-Grün-Schwäche erkannt. Der Typ lässt sich bei dieser Stärke "
                        "nicht sicher bestimmen: bitte Protan oder Deutan selbst wählen."}
    else:
        return {**base, "type": "unknown", "severity": 0.3, "angle": None,
                "note": "Keine deutliche Verwechslung. Entweder keine oder eine leichte Farbsehschwäche."}

    def dist(a: float, b: float) -> float:
        d = abs(a - b) % 180.0
        return min(d, 180.0 - d)

    dp, dd = dist(angle, AXIS_ANGLE["protan"]), dist(angle, AXIS_ANGLE["deutan"])
    if min(dp, dd) > 30.0:
        return {**base, "type": "unknown", "severity": severity, "angle": angle,
                "note": "Verwechslung erkannt, aber nicht auf der Rot-Grün-Achse. Bitte augenärztlich abklären."}
    if abs(dp - dd) < TYPE_MARGIN:
        return {**base, "type": "unknown", "severity": severity, "angle": angle,
                "note": "Rot-Grün-Verwechslung erkannt, Typ unsicher. Bitte Protan oder Deutan selbst wählen."}
    type_ = "protan" if dp < dd else "deutan"
    return {**base, "type": type_, "severity": severity, "angle": angle, "note": ""}


def suggested_profile(result: dict, fallback_type: str = "deutan"):
    """Profile from an evaluate() result; uses fallback_type if the type is unknown."""
    from .profile import Profile

    t = result["type"] if result["type"] != "unknown" else fallback_type
    return Profile.default_for(t, result["severity"])
