# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""The JavaScript profile test must score exactly like the Python one."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import profiletest as pt  # noqa: E402

JS = Path(__file__).resolve().parents[2] / "js" / "klarfarbe.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_js_profiletest_matches_python(tmp_path):
    rng = np.random.default_rng(5)
    cases = []
    for t, s in [(None, 0), ("protan", 1.0), ("deutan", 1.0), ("deutan", 0.7), ("protan", 0.8)]:
        for _ in range(10):
            cases.append([pt.simulated_order("saturated", t, s, rng), pt.simulated_order("pale", t, s, rng)])
    for _ in range(10):  # random clicking
        cases.append([list(rng.permutation(range(1, 16)) + 0), list(rng.permutation(range(1, 16)) + 0)])
    cases = [[[int(x) for x in a], [int(x) for x in b]] for a, b in cases]

    data = tmp_path / "cases.json"
    data.write_text(json.dumps(cases))
    script = (
        f"import {{ evaluateTest, testCaps }} from {json.dumps(JS.as_uri())};"
        "import fs from 'node:fs';"
        f"const c = JSON.parse(fs.readFileSync({json.dumps(str(data))}, 'utf8'));"
        "process.stdout.write(JSON.stringify({caps: testCaps('saturated'), res: c.map(([a,b]) => evaluateTest(a,b))}));"
    )
    out = json.loads(subprocess.run(["node", "--input-type=module", "-e", script],
                                    capture_output=True, text=True, check=True).stdout)
    assert np.abs(np.array(out["caps"]) - pt.caps("saturated")).max() < 1e-9
    for (a, b), js in zip(cases, out["res"]):
        py = pt.evaluate(a, b)
        assert js["type"] == py["type"] and js["severity"] == py["severity"]
        assert js["index_saturated"] == pytest.approx(py["index_saturated"], abs=1e-9)
        assert js["index_pale"] == pytest.approx(py["index_pale"], abs=1e-9)
        if py["angle"] is not None:
            d = abs(js["angle"] - py["angle"]) % 180
            assert min(d, 180 - d) < 1e-6
