# Copyright 2026 Mohammad Al-Musawi
# SPDX-License-Identifier: Apache-2.0
"""Robustness test: headless browser test of web/index.html (Playwright + Chrome)."""
import functools
import http.server
import json
import shutil
import socketserver
import sys
import threading
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klarfarbe import Profile  # noqa: E402
from klarfarbe import profiletest as pt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
CHROME = shutil.which("google-chrome") or "/usr/bin/google-chrome"

sync_api = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(not Path(CHROME).exists(), reason="Chrome not installed")


def test_index_html_is_up_to_date_with_template():
    core = (ROOT / "js" / "klarfarbe.js").read_text(encoding="utf-8")
    core = core.replace("export function", "function").replace("export const", "const")
    built = (WEB / "template.html").read_text(encoding="utf-8").replace("/*__KLARFARBE_JS__*/", core)
    assert (WEB / "index.html").read_text(encoding="utf-8") == built


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(WEB)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True, args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--enable-unsafe-swiftshader"])
        yield b
        b.close()


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(permissions=["camera", "clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and pg.errors.append(m.text))
    pg.route("**/favicon.ico", lambda r: r.fulfill(status=204, body=""))
    pg.goto(server)
    pg.wait_for_timeout(500)
    yield pg
    ctx.close()


# click the cap with index i in the current round by matching its colour
CLICK = """(i) => {
  const round = document.getElementById('roundLabel').textContent.includes('1 von 2') ? 'saturated' : 'pale';
  const c = testCaps(round)[i]; const probe = document.createElement('span');
  probe.style.background = `rgb(${c.map(v => Math.round(v * 255)).join(',')})`;
  const btn = [...document.querySelectorAll('#rowLeft button.cap')].filter(b => b.style.background === probe.style.background);
  if (btn.length !== 1) return 'match ' + btn.length; btn[0].click(); return 'ok'; }"""


def _run_test(pg, o1, o2):
    for i in list(o1) + list(o2):
        assert pg.evaluate(CLICK, int(i)) == "ok"
    pg.wait_for_timeout(100)


def test_loads_without_errors_and_webgl(page):
    assert page.evaluate("!!document.getElementById('view').getContext('webgl2')")
    assert page.inner_text("#msg") == ""
    page.wait_for_timeout(500)
    assert page.errors == []


def test_gpu_output_matches_js_core(page):
    pts = page.evaluate("""(() => { const v = document.getElementById('view'); const c = document.createElement('canvas');
      c.width = v.width; c.height = v.height; const g = c.getContext('2d'); g.drawImage(v, 0, 0);
      const p = defaultProfile('deutan', 0.6);
      return [[560,63,[72,120,50]],[720,63,[55,30,60]],[560,213,[160,80,75]],[560,513,[120,170,220]],[80,63,[176,52,58]]]
        .map(([x,y,col]) => ({x, col, gpu: Array.from(g.getImageData(x,y,1,1).data.slice(0,3)),
          exp: snapColor(col[0]/255, col[1]/255, col[2]/255, p).rgb.map(v => Math.round(v*255))})); })()""")
    for p in pts:
        if p["x"] < 480:  # left half = original
            assert p["gpu"] == p["col"]
        else:  # right half = Klarfarbe via 33^3 LUT (interpolation tolerance)
            assert max(abs(a - b) for a, b in zip(p["gpu"], p["exp"])) <= 12


def test_tabs_switch(page):
    page.click("#navTest")
    page.wait_for_timeout(100)
    assert page.is_visible("#profiltest") and page.is_hidden("#demo")
    assert page.get_attribute("#navTest", "aria-current") == "page"
    page.click("#navDemo")
    page.wait_for_timeout(100)
    assert page.is_visible("#demo") and page.is_hidden("#profiltest")


def test_profile_test_perfect_order(page):
    page.click("#navTest")
    _run_test(page, range(1, 16), range(1, 16))
    assert page.is_visible("#testResult")
    assert "keine oder leicht" in page.inner_text("#resultText")


def test_profile_test_simulated_deutan_and_apply(page):
    rng = np.random.default_rng(2)
    o1 = pt.simulated_order("saturated", "deutan", 1.0, rng)
    o2 = pt.simulated_order("pale", "deutan", 1.0, rng)
    py = pt.evaluate(o1, o2)
    page.click("#navTest")
    _run_test(page, o1, o2)
    assert "Deutan" in page.inner_text("#resultText") and py["type"] == "deutan"
    page.click("#applyProfile")
    page.wait_for_timeout(200)
    assert page.evaluate("location.hash") == "#demo"
    assert float(page.input_value("#sev")) == pytest.approx(0.85)
    assert page.get_attribute("#tDeutan", "aria-pressed") == "true"
    assert page.errors == []


def test_undo_removes_last_pick(page):
    page.click("#navTest")
    for i in (1, 2, 3):
        page.evaluate(CLICK, i)
    page.click("#undo")
    assert page.evaluate("document.querySelectorAll('#rowDone .cap.small').length") == 2


def test_type_choice_buttons_match_applied_type(page):
    page.click("#tProtan")
    page.click("#navTest")
    _run_test(page, range(1, 16), range(1, 16))  # -> type unknown, choice shown
    shown = "deutan" if page.get_attribute("#chooseDeutan", "aria-pressed") == "true" else "protan"
    page.click("#applyProfile")
    page.wait_for_timeout(100)
    applied = "deutan" if page.get_attribute("#tDeutan", "aria-pressed") == "true" else "protan"
    assert shown == applied


def test_export_cube_and_profile(page):
    page.click("#copyCube")
    page.wait_for_timeout(400)
    lines = page.input_value("#out").strip().split("\n")
    assert lines[:4] == ['TITLE "Klarfarbe"', "LUT_3D_SIZE 33", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    data = np.array([[float(x) for x in ln.split()] for ln in lines[4:]])
    assert data.shape == (33 ** 3, 3) and data.min() >= 0 and data.max() <= 1
    page.click("#copyProfile")
    page.wait_for_timeout(200)
    prof = Profile.from_dict(json.loads(page.input_value("#out")))
    assert prof.type == "deutan" and prof.severity == pytest.approx(0.6)


def test_camera_and_glasses_mode(page):
    page.click("#srcCam")
    page.wait_for_timeout(2000)
    assert page.inner_text("#msg") == ""
    assert page.get_attribute("#srcCam", "aria-pressed") == "true"
    w, h = page.evaluate("[view.width, view.height]")
    assert w > 0 and h > 0
    fps = page.evaluate("""new Promise(r => { let n = 0; const t0 = performance.now();
      (function f() { n++; if (performance.now() - t0 < 1500) requestAnimationFrame(f); else r(n * 1000 / (performance.now() - t0)); })(); })""")
    assert fps > 3  # headless SwiftShader; real devices are much faster
    page.click("#glassFull")
    page.wait_for_timeout(500)
    assert page.evaluate("document.body.classList.contains('glasses')")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    assert not page.evaluate("document.body.classList.contains('glasses')")
    assert page.errors == []


def test_broken_file_upload_shows_message(page, tmp_path):
    f = tmp_path / "broken.png"
    f.write_bytes(b"not an image")
    page.set_input_files("#file", str(f))
    page.wait_for_timeout(400)
    assert "nicht gelesen" in page.inner_text("#msg")
