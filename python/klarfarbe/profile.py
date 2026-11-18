# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Personal colour-vision profile (format: spec/profile-format.md)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

FORMAT_NAME = "klarfarbe-profile"
FORMAT_VERSION = "0.1"
TYPES = ("protan", "deutan", "unknown")


@dataclass
class Target:
    """Per-category override of the snapping target (Oklab LCh units)."""

    hue_shift_deg: float = 0.0  # rotate the prototype hue
    min_lightness: float | None = None  # lift dark colours to at least this L


@dataclass
class Profile:
    type: str = "unknown"
    severity: float = 0.5  # 0 = mild, 1 = strong
    threshold: float = 0.5  # minimum confidence before snapping starts
    strength: float = 0.85  # how far a confident colour moves to its target
    protect_skin: bool = True  # leave skin tones (and similar browns) unchanged
    max_chroma_gain: float = 2.0  # a colour gets at most this much more saturated
    targets: dict[str, Target] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in TYPES:
            raise ValueError(f"type must be one of {TYPES}, got {self.type!r}")
        for name in ("severity", "threshold", "strength"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")
        if self.max_chroma_gain < 1.0:
            raise ValueError("max_chroma_gain must be >= 1")

    @classmethod
    def default_for(cls, type_: str, severity: float = 0.5) -> "Profile":
        """Starting values until the profile test exists.

        Red-green confusion is reduced by pushing green towards blue-green
        (the blue-yellow axis stays intact) and by lifting dark reds and
        purples, which protans in particular see as near-black.
        """
        s = severity
        targets = {
            "green": Target(hue_shift_deg=20.0 * s),
            "purple": Target(min_lightness=0.45 + 0.1 * s),
            "brown": Target(min_lightness=0.38),
        }
        if type_ == "protan":
            targets["red"] = Target(hue_shift_deg=-6.0 * s, min_lightness=0.5 + 0.1 * s)
        else:
            targets["red"] = Target(min_lightness=0.5)
        return cls(type=type_, severity=s, targets=targets)

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
            "targets": {k: asdict(v) for k, v in self.targets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        if data.get("format") != FORMAT_NAME:
            raise ValueError("not a klarfarbe profile")
        from dataclasses import fields
        target_fields = {f.name for f in fields(Target)}
        targets = {
            k: Target(**{tk: tv for tk, tv in v.items() if tk in target_fields})
            for k, v in data.get("targets", {}).items()
            if isinstance(v, dict)
        }
        allowed_profile = {f.name for f in fields(cls)}
        profile_kwargs = {k: v for k, v in data.items() if k in allowed_profile and k != "targets"}
        return cls(targets=targets, **profile_kwargs)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Profile":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
