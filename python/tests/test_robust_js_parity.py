# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Robustness test: Python <-> JS parity on random profiles, edge colours, LUT and .cube text."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile, Target, build_lut, snap_srgb, write_cube  # noqa: E402
from klarfarbe.categories import KEYS, classify  # noqa: E402
from klarfarbe.oklab import lab_to_lch, srgb_to_oklab  # noqa: E402
from klarfarbe.snap import snap_lab  # noqa: E402

JS = Path(__file__).resolve().parents[2] / "js" / "klarfarbe.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _profiles():
    rng = np.random.default_rng(99)
    out = []
    for _ in range(10):
        out.append(Profile(
            type=str(rng.choice(["protan", "deutan", "unknown"])), severity=float(rng.random()),
            threshold=float(rng.random()), strength=float(rng.random()), protect_skin=bool(rng.random() < 0.5),
            max_chroma_gain=float(1 + 3 * rng.random()),
            targets={k: Target(float(rng.normal(0, 30)), None if rng.random() < 0.5 else float(rng.random()))
                     for k in KEYS if rng.random() < 0.6}))
    out.append(Profile(threshold=0.0, strength=1.0))
    out.append(Profile(threshold=1.0, strength=1.0))
    return out


def _node(script):
    res = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


@pytest.fixture(scope="module")
def js_results(tmp_path_factory):
    rng = np.random.default_rng(1)
    edge = [[0, 0, 0], [1, 1, 1], [.5, .5, .5], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [0, 1, 1], [1, 0, 1],
            [1e-9, 0, 0], [1, 1, 1 - 1e-9], [0.04045, 0.04045, 0.0405]]
    cols = np.concatenate([np.array(edge), rng.random((3000, 3)), rng.integers(0, 256, (2000, 3)) / 255])
    profs = _profiles()
    data = tmp_path_factory.mktemp("js") / "in.json"
    data.write_text(json.dumps({"profiles": [p.to_dict() for p in profs], "colours": cols.tolist()}))
    script = (
        f"import {{ snapColor, buildCube, buildLutRGBA }} from {json.dumps(JS.as_uri())};"
        "import fs from 'node:fs';"
        f"const d = JSON.parse(fs.readFileSync({json.dumps(str(data))}, 'utf8'));"
        "const out = d.profiles.map(p => d.colours.map(([r,g,b]) => { const s = snapColor(r,g,b,p);"
        "  return [s.rgb[0], s.rgb[1], s.rgb[2], s.confidence, s.category]; }));"
        "const cube = buildCube(d.profiles[0], 9, 'T'); const lut = Array.from(buildLutRGBA(d.profiles[0], 9));"
        "process.stdout.write(JSON.stringify({out, cube, lut}));"
    )
    return profs, cols, _node(script)


def test_rgb_confidence_category_parity(js_results):
    profs, cols, res = js_results
    pc, _ = classify(lab_to_lch(srgb_to_oklab(cols)))
    py_cats = [KEYS[i] for i in pc.argmax(-1)]
    for p, rows in zip(profs, res["out"]):
        arr = np.array([r[:4] for r in rows], float)
        assert np.abs(arr[:, :3] - snap_srgb(cols, p)).max() < 1e-9
        _, conf = snap_lab(srgb_to_oklab(cols), p)
        assert np.abs(arr[:, 3] - conf).max() < 1e-9
        assert [r[4] for r in rows] == py_cats


def test_cube_text_identical(js_results, tmp_path):
    profs, _, res = js_results
    path = tmp_path / "py.cube"
    write_cube(build_lut(profs[0], 9), path, "T")
    assert path.read_text() == res["cube"]


def test_rgba_lut_matches_python(js_results):
    profs, _, res = js_results
    js = np.array(res["lut"]).reshape(9, 9, 9, 4)  # [b, g, r, rgba]
    assert (js[..., 3] == 255).all()
    py = np.round(build_lut(profs[0], 9) * 255).astype(int)
    assert np.abs(js[..., :3].transpose(2, 1, 0, 3) - py).max() == 0


def _assert_close(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a:
            _assert_close(a[k], b[k])
    elif isinstance(a, float) and not isinstance(a, bool):
        assert a == pytest.approx(b, abs=1e-12)
    else:
        assert a == b


def test_js_profile_defaults_match_python():
    out = _node(f"import {{ defaultProfile }} from {json.dumps(JS.as_uri())};"
                "process.stdout.write(JSON.stringify(['deutan','protan'].flatMap(t => [0, 0.35, 1].map(s => defaultProfile(t, s)))));")
    i = 0
    for t in ("deutan", "protan"):
        for s in (0, 0.35, 1):
            _assert_close(Profile.from_dict(out[i]).to_dict(), Profile.default_for(t, s).to_dict())
            i += 1
