# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""js/klarfarbe.js must give the same results as the Python reference."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile, snap_srgb  # noqa: E402

JS = Path(__file__).resolve().parents[2] / "js" / "klarfarbe.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _profiles():
    a = Profile.default_for("deutan", 0.6)
    b = Profile.default_for("protan", 0.9)
    b.protect_skin = False
    c = Profile.default_for("deutan", 0.2)
    c.threshold = 1.0
    return [a, b, c]


@pytest.mark.parametrize("profile", _profiles(), ids=["deutan", "protan-handwerk", "threshold-1"])
def test_js_matches_python(profile, tmp_path):
    colours = np.random.default_rng(42).random((5000, 3))
    expected = snap_srgb(colours, profile)

    data = tmp_path / "in.json"
    data.write_text(json.dumps({"profile": profile.to_dict(), "colours": colours.tolist()}))
    script = (
        f"import {{ snapColor }} from {json.dumps(JS.as_uri())};"
        "import fs from 'node:fs';"
        f"const d = JSON.parse(fs.readFileSync({json.dumps(str(data))}, 'utf8'));"
        "const out = d.colours.map(([r,g,b]) => snapColor(r,g,b,d.profile).rgb);"
        "process.stdout.write(JSON.stringify(out));"
    )
    res = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    got = np.array(json.loads(res.stdout))
    assert np.abs(got - expected).max() < 1e-6
