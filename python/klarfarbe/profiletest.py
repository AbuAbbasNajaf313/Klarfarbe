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

It only sets software parameters for Klarfarbe. It is not a medical
device and not a diagnostic or fitness test (see DISCLAIMER).
"""
from __future__ import annotations

import numpy as np

from .oklab import lch_to_lab, oklab_to_srgb, srgb_to_oklab

N_CAPS = 15
LIGHTNESS = 0.68
# Cap chroma (Oklab). "saturated" has about the colour steps of the
# Farnsworth D-15, "pale" lies between the D-15 and the desaturated D-15d.
CHROMA = {"saturated": 0.06, "pale": 0.035}

DISCLAIMER = ("Klarfarbe ist eine Sehhilfe-Software, kein Medizinprodukt und kein "
              "Diagnose- oder Eignungstest.")
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


def validate_order(order) -> list[int]:
    """The order must be a permutation of the caps 1..N_CAPS, else ValueError."""
    try:
        out = [int(i) for i in order]
    except (TypeError, ValueError):
        raise ValueError("order must be a list of cap numbers") from None
    if any(int(i) != i for i in order) or sorted(out) != list(range(1, N_CAPS + 1)):
        raise ValueError(f"order must contain each cap 1..{N_CAPS} exactly once")
    return out


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
    mo = moments(validate_order(order), caps(round_))
    return mo["major"] / _perfect_major(round_), mo["angle"]


def _scatter(order: list[int], round_: str) -> np.ndarray:
    """2x2 scatter of neighbour differences, normalised by the perfect order."""
    pts = _ab(caps(round_)[[0] + list(order)])
    d = np.diff(pts, axis=0)
    return (d.T @ d) / (len(d) * _perfect_major(round_) ** 2)


def combined_axis(order_saturated: list[int], order_pale: list[int]) -> float:
    """Confusion axis (degrees, [-90, 90)) from both rounds together.

    Summing the normalised scatter matrices of both rounds halves the
    angle noise compared with one round, so the type is wrong less often.
    """
    m = _scatter(validate_order(order_saturated), "saturated") + _scatter(validate_order(order_pale), "pale")
    a, b, c = m[0, 0], m[0, 1], m[1, 1]
    angle = 0.5 * np.degrees(np.arctan2(2.0 * b, a - c))
    return float((angle + 90.0) % 180.0 - 90.0)


def selectivity(order: list[int], round_: str) -> float:
    """S = major / minor radius (Vingrys & King-Smith). Random orders give S near 1."""
    mo = moments(validate_order(order), caps(round_))
    return mo["major"] / max(mo["minor"], 1e-12)


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


def _combined(ci_s: float, ci_p: float) -> float:
    return float(np.sqrt(ci_s * ci_p))


def calibrate(trials: int = 40, seed: int = 0) -> dict:
    """Detection rate and median axis angle per type and severity (simulated observers)."""
    rng = np.random.default_rng(seed)
    out = {}
    for t in ("protan", "deutan", None):
        rows = []
        for s in (np.round(np.arange(0.3, 1.01, 0.1), 2) if t else [0.0]):
            res = []
            for _ in range(trials):
                o_s = simulated_order("saturated", t, float(s), rng)
                o_p = simulated_order("pale", t, float(s), rng)
                ci_s, ang = confusion_index(o_s, "saturated")
                ci_p, _ = confusion_index(o_p, "pale")
                res.append((ci_s, ci_p, ang))
            r = np.array(res)
            strong = (r[:, 0] > STRONG_INDEX) | (np.sqrt(r[:, 0] * r[:, 1]) > STRONG_COMBINED)
            rows.append({"severity": float(s),
                         "strong_rate": float(strong.mean()),
                         "any_rate": float((strong | (np.sqrt(r[:, 0] * r[:, 1]) > FAIL_INDEX)).mean()),
                         "angle": float(np.median(r[strong, 2])) if strong.any() else None})
        out[t or "normal"] = rows
    return out


# Calibrated with simulated observers (Machado 2009 matrices, perception
# noise SIM_NOISE, 600 normal and 200 CVD runs per cell):
# - Strong: saturated round above STRONG_INDEX or both rounds (geometric
#   mean) above STRONG_COMBINED. Strong forms (severity 1.0) reach it in
#   100 %, normals never (also not at 1.7 x noise).
# - FAIL_INDEX on the geometric mean of both rounds: normals exceed it in 0 %
#   at SIM_NOISE and in about 8 % at 1.7 x SIM_NOISE (old caps and rule: 30 %);
#   severity 0.7 is caught in about 80 %.
# - Median axes of strong forms (both rounds combined): protan +8, deutan
#   -3.5 degrees in Oklab a/b. Closer than TYPE_MARGIN to both: type unsure.
# - Random clicking gives a selectivity S near 1; a type is only reported for
#   S >= MIN_SELECTIVITY (random orders: about 2 %).
# These are model values, not norms from real people.
STRONG_INDEX = 2.4
STRONG_COMBINED = 2.6
FAIL_INDEX = 1.9
AXIS_ANGLE = {"protan": 8.0, "deutan": -3.5}
TYPE_MARGIN = 3.0
MIN_SELECTIVITY = 1.8

NOTES = {
    "none": "Deine Reihenfolge war nahezu fehlerfrei. Klarfarbe startet mit einer leichten "
            "Einstellung. Du kannst sie in der Demo anpassen.",
    "moderate": "Deine Reihenfolge passt zu einer mittleren Einstellung. Welche Achse besser hilft, "
                "ist hier nicht eindeutig: probiere Protan und Deutan in der Demo aus.",
    "unsystematic": "Deine Reihenfolge wirkt unsystematisch. Bitte wiederhole den Test in Ruhe. "
                    "Bis dahin startet Klarfarbe mit einer starken Einstellung; welche Achse hilft, wählst du selbst.",
    "off_axis": "Deine Reihenfolge weicht ab, aber nicht so, wie es bei Rot-Grün-Schwäche typisch ist. "
                "Klarfarbe ist dafür womöglich nicht die passende Hilfe. Wenn du dein Farbsehen genau "
                "wissen willst, kann das eine Augenarztpraxis prüfen.",
    "type_unsure": "Welche Achse besser hilft, ist nicht eindeutig: probiere Protan und Deutan in der Demo aus.",
    "typed": "",
}


def evaluate(order_saturated: list[int], order_pale: list[int]) -> dict:
    """Turn two arrangements into a suggested starting setting (not a diagnosis).

    Severity is coarse on purpose (0.3 / 0.6 / 0.85). A type (protan/deutan)
    is only suggested for a strong, systematic confusion along one axis.
    Raises ValueError if an order is not a permutation of the caps 1..15.
    """
    ci_s, ang_s = confusion_index(order_saturated, "saturated")
    ci_p, ang_p = confusion_index(order_pale, "pale")
    sel = selectivity(order_saturated, "saturated")
    base = {"index_saturated": ci_s, "index_pale": ci_p, "selectivity": sel}

    def result(type_, severity, angle, key):
        return {**base, "type": type_, "severity": severity, "angle": angle,
                "note_key": key, "note": NOTES[key]}

    comb = _combined(ci_s, ci_p)
    if not (ci_s > STRONG_INDEX or comb > STRONG_COMBINED):
        if comb > FAIL_INDEX:
            return result("unknown", 0.6, ang_p, "moderate")
        return result("unknown", 0.3, None, "none")
    if sel < MIN_SELECTIVITY:
        return result("unknown", 0.85, ang_s, "unsystematic")
    angle = combined_axis(order_saturated, order_pale)

    def dist(a: float, b: float) -> float:
        d = abs(a - b) % 180.0
        return min(d, 180.0 - d)

    dp, dd = dist(angle, AXIS_ANGLE["protan"]), dist(angle, AXIS_ANGLE["deutan"])
    if min(dp, dd) > 30.0:
        return result("unknown", 0.85, angle, "off_axis")
    if abs(dp - dd) < TYPE_MARGIN:
        return result("unknown", 0.85, angle, "type_unsure")
    return result("protan" if dp < dd else "deutan", 0.85, angle, "typed")


def suggested_profile(result: dict, fallback_type: str = "deutan"):
    """Profile from an evaluate() result; uses fallback_type if the type is unknown."""
    from .profile import Profile

    t = result["type"] if result["type"] != "unknown" else fallback_type
    return Profile.default_for(t, result["severity"])
