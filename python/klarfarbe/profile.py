# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Personal colour-vision profile (format: spec/profile-format.md)."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

FORMAT_NAME = "klarfarbe-profile"
FORMAT_VERSION = "0.1"
TYPES = ("protan", "deutan", "unknown")
MODES = ("standard", "elektro")
MAX_CHROMA_GAIN_RANGE = (1.0, 4.0)


def _number(value, name: str, lo: float | None = None, hi: float | None = None) -> float:
    """A finite real number (not bool) inside [lo, hi], else ValueError."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise ValueError(f"{name} must be in [{lo}, {hi}], got {value}")
    return value


def _optional(value, name: str, lo: float, hi: float) -> float | None:
    return None if value is None else _number(value, name, lo, hi)


def _boolean(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false, got {value!r}")
    return value


@dataclass
class Target:
    """Per-category override of the snapping target (Oklab LCh units)."""

    hue_shift_deg: float = 0.0  # rotate the prototype hue, in [-180, 180]
    min_lightness: float | None = None  # lift dark colours to at least this L
    min_chroma: float | None = None  # target chroma instead of the prototype's

    def __post_init__(self) -> None:
        self.hue_shift_deg = _number(self.hue_shift_deg, "hue_shift_deg", -180.0, 180.0)
        self.min_lightness = _optional(self.min_lightness, "min_lightness", 0.0, 1.0)
        self.min_chroma = _optional(self.min_chroma, "min_chroma", 0.0, 0.4)

    def to_dict(self) -> dict:
        return {"hue_shift_deg": self.hue_shift_deg, "min_lightness": self.min_lightness,
                "min_chroma": self.min_chroma}

    @classmethod
    def from_dict(cls, data, key: str = "?") -> "Target":
        if not isinstance(data, dict):
            raise ValueError(f"targets.{key} must be an object")
        # unknown fields are ignored (forward compatibility)
        return cls(**{k: data[k] for k in ("hue_shift_deg", "min_lightness", "min_chroma") if k in data})


@dataclass
class Profile:
    type: str = "unknown"
    severity: float = 0.5  # 0 = mild, 1 = strong
    threshold: float = 0.5  # minimum confidence before snapping starts
    strength: float = 0.85  # how far a confident colour moves to its target
    protect_skin: bool = True  # leave skin tones (and similar browns) unchanged
    max_chroma_gain: float = 2.0  # a colour gets at most this much more saturated
    clip_guard: bool = True  # do not snap over-exposed pixels (a channel near 255)
    mode: str = "standard"  # "elektro": cable colours (IEC 60445), no skin protection
    targets: dict[str, Target] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in TYPES:
            raise ValueError(f"type must be one of {TYPES}, got {self.type!r}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        for name in ("severity", "threshold", "strength"):
            setattr(self, name, _number(getattr(self, name), name, 0.0, 1.0))
        self.max_chroma_gain = _number(self.max_chroma_gain, "max_chroma_gain", *MAX_CHROMA_GAIN_RANGE)
        self.protect_skin = _boolean(self.protect_skin, "protect_skin")
        self.clip_guard = _boolean(self.clip_guard, "clip_guard")
        if not isinstance(self.targets, dict):
            raise ValueError("targets must be an object")
        for key, t in self.targets.items():
            if not isinstance(t, Target):
                raise ValueError(f"targets.{key} must be a Target")

    @classmethod
    def default_for(cls, type_: str, severity: float = 0.5, mode: str = "standard") -> "Profile":
        """Starting values until a personal profile exists.

        Model basis (simulated observers, Machado 2009 / Vienot 1999), checked
        by tests/test_benefit.py:
        - deutan/unknown: green is lifted (green against red and grey by
          lightness) and, for strong forms, turned past the deutan neutral hue
          (about 176 degrees Oklab) towards blue-green. The turn grows with
          severity cubed (7.5 degrees at 0.5, 60 at 1.0): a medium turn would
          land green on the neutral hue, where it looks grey. Dark reds are
          lifted to L 0.5.
        - protan: red is turned towards orange, away from the protan neutral
          hue (about 11 degrees), and dark reds are lifted only to L 0.5: a
          stronger lift moves red onto the lightness of grey for protans.
          Green is turned only slightly (15 degrees at 1.0, the protan neutral
          hue is near 188) and separated from red by lightness.
        - purple is lifted well above blue, which dichromats see as the same hue.
        Mode "elektro" switches skin protection off and separates the cable
        colours of IEC 60445 (brown, blue, green-yellow against black and grey)
        more strongly. It is not a safety function.
        """
        s = _number(severity, "severity", 0.0, 1.0)
        targets = {"brown": Target(min_lightness=0.38)}
        if type_ == "protan":
            targets["red"] = Target(hue_shift_deg=12.0 * s, min_lightness=0.5)
            targets["green"] = Target(hue_shift_deg=15.0 * s, min_lightness=0.62 + 0.08 * s)
            targets["purple"] = Target(hue_shift_deg=-10.0 * s, min_lightness=0.55 + 0.10 * s)
        else:
            targets["red"] = Target(hue_shift_deg=0.0, min_lightness=0.5)
            targets["green"] = Target(hue_shift_deg=60.0 * s ** 3, min_lightness=0.62 + 0.08 * s)
            targets["purple"] = Target(hue_shift_deg=-10.0 * s, min_lightness=0.55 + 0.10 * s)
        protect_skin = True
        if mode == "elektro":
            protect_skin = False
            targets["brown"] = Target(hue_shift_deg=8.0, min_lightness=0.40, min_chroma=0.12)
            targets["blue"] = Target(min_lightness=0.5)
            targets["yellow"] = Target(min_lightness=0.8)
        return cls(type=type_, severity=s, protect_skin=protect_skin, mode=mode, targets=targets)

    def to_dict(self) -> dict:
        return {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "type": self.type,
            "severity": self.severity,
            "threshold": self.threshold,
            "strength": self.strength,
            "protect_skin": self.protect_skin,
            "max_chroma_gain": self.max_chroma_gain,
            "clip_guard": self.clip_guard,
            "mode": self.mode,
            "targets": {k: v.to_dict() for k, v in self.targets.items()},
        }

    @classmethod
    def from_dict(cls, data) -> "Profile":
        """Validate and read a profile. Raises ValueError for anything invalid.

        Unknown fields and unknown categories are ignored, as the spec requires.
        """
        from .categories import KEYS

        if not isinstance(data, dict):
            raise ValueError("a profile must be a JSON object")
        if data.get("format") != FORMAT_NAME:
            raise ValueError("not a klarfarbe profile")
        if not isinstance(data.get("version", FORMAT_VERSION), str):
            raise ValueError("version must be a string")
        # newer versions are read as far as this reader understands them
        for key in ("type", "severity"):
            if key not in data:
                raise ValueError(f"missing field {key!r}")
        raw_targets = data.get("targets", {})
        if not isinstance(raw_targets, dict):
            raise ValueError("targets must be an object")
        targets = {k: Target.from_dict(v, k) for k, v in raw_targets.items() if k in KEYS}
        return cls(
            type=data["type"],
            severity=data["severity"],
            threshold=data.get("threshold", 0.5),
            strength=data.get("strength", 0.85),
            protect_skin=data.get("protect_skin", True),
            max_chroma_gain=data.get("max_chroma_gain", 2.0),
            clip_guard=data.get("clip_guard", True),
            mode=data.get("mode", "standard"),
            targets=targets,
        )

    def save(self, path: str | Path) -> None:
        text = json.dumps(self.to_dict(), indent=2, allow_nan=False)
        Path(path).write_text(text, encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Profile":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
