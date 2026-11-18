# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Public JS API must match Python: constants, presets, validation, texts."""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import LUT_N, Profile, build_lut, snap_srgb, write_cube  # noqa: E402
from klarfarbe import profiletest as pt  # noqa: E402

JS = Path(__file__).resolve().parents[2] / "js" / "klarfarbe.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _node(body, data=None, tmp=None):
    pre = f"import * as K from {json.dumps(JS.as_uri())}; import fs from 'node:fs';"
    if data is not None:
        f = tmp / "d.json"
        f.write_text(json.dumps(data))
        pre += f"const D = JSON.parse(fs.readFileSync({json.dumps(str(f))}, 'utf8'));"
    res = subprocess.run(["node", "--input-type=module", "-e", pre + body], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def _close(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a:
            _close(a[k], b[k])
    elif isinstance(a, float):
        assert a == pytest.approx(b, abs=1e-12)
    else:
        assert a == b


def test_constants_match():
    out = _node("process.stdout.write(JSON.stringify([K.LUT_N, K.DISCLAIMER, K.TEST_NOTES]));")
    assert out[0] == LUT_N == 64
    assert out[1] == pt.DISCLAIMER
    assert out[2] == pt.NOTES


def test_elektro_preset_and_snap_parity(tmp_path):
    cols = np.random.default_rng(3).random((3000, 3))
    profs = []
    for t in ("protan", "deutan"):
        e = Profile.default_for(t, 0.7, mode="elektro")
        e.clip_guard = False
        profs.append(e)
    out = _node("process.stdout.write(JSON.stringify({p: [K.defaultProfile('protan', 0.7, {mode: 'elektro'}),"
                " K.defaultProfile('deutan', 0.7, {mode: 'elektro'})], s: D.profiles.map(p => D.cols.map(c => K.snapColor(...c, p).rgb))}));",
                {"profiles": [p.to_dict() for p in profs], "cols": cols.tolist()}, tmp_path)
    for js, t in zip(out["p"], ("protan", "deutan")):
        py = Profile.default_for(t, 0.7, mode="elektro").to_dict()
        _close(Profile.from_dict(js).to_dict(), py)
        assert js["mode"] == "elektro" and js["protect_skin"] is False
    for p, rows in zip(profs, out["s"]):
        assert np.abs(np.array(rows) - snap_srgb(cols, p)).max() < 1e-9


BAD = [
    {"format": "x", "type": "deutan", "severity": 0.5},
    {"format": "klarfarbe-profile", "severity": 0.5},
    {"format": "klarfarbe-profile", "type": "deutan", "severity": 1.5},
    {"format": "klarfarbe-profile", "type": "deutan", "severity": 0.5, "protect_skin": "false"},
    {"format": "klarfarbe-profile", "type": "deutan", "severity": 0.5, "max_chroma_gain": 5},
    {"format": "klarfarbe-profile", "type": "deutan", "severity": 0.5, "targets": []},
    {"format": "klarfarbe-profile", "type": "deutan", "severity": 0.5, "targets": {"red": {"min_lightness": 2}}},
    {"format": "klarfarbe-profile", "type": "deutan", "severity": 0.5, "mode": "werkstatt"},
    [1, 2],
]


def test_validate_profile_rejects_like_python(tmp_path):
    out = _node("process.stdout.write(JSON.stringify(D.map(d => { try { K.validateProfile(d); return 'ok'; }"
                " catch (e) { return e.name; } })));", BAD, tmp_path)
    assert out == ["RangeError"] * len(BAD)
    for d in BAD:
        with pytest.raises(ValueError):
            Profile.from_dict(d)


def test_validate_profile_ignores_unknown(tmp_path):
    d = {"format": "klarfarbe-profile", "version": "9.9", "type": "deutan", "severity": 0.5, "future": 1,
         "targets": {"green": {"hue_shift_deg": 15, "later": 1}, "violet": {"hue_shift_deg": 3}}}
    js = _node("process.stdout.write(JSON.stringify(K.validateProfile(D)));", d, tmp_path)
    assert js["targets"].keys() == {"green"} and "future" not in js
    _close(Profile.from_dict(js).to_dict(), Profile.from_dict(d).to_dict())


def test_invalid_order_throws(tmp_path):
    orders = [[1] * 15, list(range(1, 15)), list(range(0, 15)), []]
    out = _node("process.stdout.write(JSON.stringify(D.map(o => { try { K.evaluateTest(o, o); return 'ok'; }"
                " catch (e) { return e.name; } })));", orders, tmp_path)
    assert out == ["RangeError"] * 4


def test_cube_title_sanitised_identically(tmp_path):
    title = 'a"b\nLUT_3D_SIZE 99'
    p = Profile.default_for("deutan", 0.6)
    js = _node(f"process.stdout.write(JSON.stringify(K.buildCube(D, 3, {json.dumps(title)})));", p.to_dict(), tmp_path)
    write_cube(build_lut(p, 3), tmp_path / "t.cube", title)
    assert js == (tmp_path / "t.cube").read_text()
    assert js.splitlines()[0] == "TITLE \"a'b\""


def test_profiletest_note_and_selectivity_parity(tmp_path):
    rng = np.random.default_rng(9)
    cases = [[[int(x) for x in rng.permutation(15) + 1], [int(x) for x in rng.permutation(15) + 1]] for _ in range(20)]
    for t, s in [(None, 0), ("protan", 1.0), ("deutan", 1.0), ("deutan", 0.7)]:
        for _ in range(5):
            cases.append([pt.simulated_order("saturated", t, s, rng), pt.simulated_order("pale", t, s, rng)])
    out = _node("process.stdout.write(JSON.stringify(D.map(([a, b]) => K.evaluateTest(a, b))));", cases, tmp_path)
    for (a, b), js in zip(cases, out):
        py = pt.evaluate(a, b)
        assert js["note_key"] == py["note_key"] and js["note"] == py["note"]
        assert math.isclose(js["selectivity"], py["selectivity"], rel_tol=1e-9)
