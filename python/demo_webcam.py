# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Live webcam demo: left original, right with Klarfarbe.

Start:  python demo_webcam.py --type deutan --severity 0.6

Keys:
  q   quit
  v   switch view (side by side / Klarfarbe only)
  h   skin-tone protection on/off (off = Handwerk mode, e.g. cable colours)
  t   switch type protan / deutan
  + - raise / lower the confidence threshold
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

from klarfarbe import Profile
from klarfarbe.snap import apply_lut_fast, build_lut

LUT_SIZE = 64


def main() -> int:
    try:
        import cv2
    except ImportError:
        print("Bitte zuerst installieren: pip install -r requirements.txt", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=("protan", "deutan"), default="deutan")
    parser.add_argument("--severity", type=float, default=0.5)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    prof = Profile.default_for(args.type, args.severity)
    lut = build_lut(prof, LUT_SIZE)
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("Kamera nicht verfuegbar. Unter macOS: Systemeinstellungen > Datenschutz > Kamera "
              "fuer das Terminal erlauben.", file=sys.stderr)
        return 1

    side_by_side = True
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        scale = 640 / frame.shape[1]
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        snapped = cv2.cvtColor(apply_lut_fast(rgb, lut), cv2.COLOR_RGB2BGR)

        view = np.hstack([frame, snapped]) if side_by_side else snapped
        status = (f"{prof.type}  Schwelle {prof.threshold:.2f}  "
                  f"Hautschutz {'an' if prof.protect_skin else 'aus'}")
        cv2.putText(view, status, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow("Klarfarbe", view)

        key = cv2.waitKey(1) & 0xFF
        rebuild = False
        if key == ord("q"):
            break
        if key == ord("v"):
            side_by_side = not side_by_side
        elif key == ord("h"):
            prof.protect_skin = not prof.protect_skin
            rebuild = True
        elif key == ord("t"):
            new_type = "protan" if prof.type == "deutan" else "deutan"
            keep = (prof.threshold, prof.protect_skin)
            prof = Profile.default_for(new_type, prof.severity)
            prof.threshold, prof.protect_skin = keep
            rebuild = True
        elif key in (ord("+"), ord("=")):
            prof.threshold = min(0.95, prof.threshold + 0.05)
            rebuild = True
        elif key == ord("-"):
            prof.threshold = max(0.05, prof.threshold - 0.05)
            rebuild = True
        if rebuild:
            lut = build_lut(prof, LUT_SIZE)

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
