# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Command line: snap a photo, export a .cube LUT, or create a profile.

    python -m klarfarbe.cli image foto.jpg foto_klar.jpg --type deutan --severity 0.6
    python -m klarfarbe.cli cube klarfarbe.cube --type protan
    python -m klarfarbe.cli profile mein_profil.json --type deutan --severity 0.7
"""
from __future__ import annotations

import argparse
import sys

from .profile import TYPES, Profile
from .snap import apply_lut, build_lut, write_cube


def _profile(args: argparse.Namespace) -> Profile:
    if args.profile:
        prof = Profile.load(args.profile)
    else:
        prof = Profile.default_for(args.type, args.severity)
    if args.handwerk:
        prof.protect_skin = False
    return prof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="klarfarbe")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("image", "cube", "profile"):
        p = sub.add_parser(name)
        p.add_argument("--type", choices=TYPES, default="deutan")
        p.add_argument("--severity", type=float, default=0.5)
        p.add_argument("--profile", help="JSON-Profil statt --type/--severity")
        p.add_argument("--handwerk", action="store_true", help="Hautton-Schutz aus, z. B. fuer Aderfarben")
        if name == "image":
            p.add_argument("input")
            p.add_argument("output")
        else:
            p.add_argument("output")
    args = parser.parse_args(argv)
    prof = _profile(args)

    if args.cmd == "profile":
        prof.save(args.output)
    elif args.cmd == "cube":
        write_cube(build_lut(prof, 33), args.output)
    else:
        try:
            import cv2
        except ImportError:
            print("Bitte zuerst installieren: pip install opencv-python", file=sys.stderr)
            return 1
        bgr = cv2.imread(args.input)
        if bgr is None:
            print(f"Bild nicht lesbar: {args.input}", file=sys.stderr)
            return 1
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        out = apply_lut(rgb, build_lut(prof, 33))
        cv2.imwrite(args.output, cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    print(f"Fertig: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
