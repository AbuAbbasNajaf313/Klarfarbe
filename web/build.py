# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Build web/index.html: one self-contained page with js/klarfarbe.js inlined.

    python web/build.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
core = (ROOT / "js" / "klarfarbe.js").read_text(encoding="utf-8")
core = core.replace("export function", "function").replace("export const", "const")
template = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
page = template.replace("/*__KLARFARBE_JS__*/", core)
(ROOT / "web" / "index.html").write_text(page, encoding="utf-8")
print("web/index.html geschrieben,", len(page), "Zeichen")
