// Copyright 2026 Mohammad Al-Musawi
// SPDX-License-Identifier: Apache-2.0
//
// Klarfarbe core in plain JavaScript (no dependencies).
// Mirrors python/klarfarbe exactly; tests/compare_python.mjs checks this.
// Works in browsers, Node.js and Adobe UXP.

const TAU = 2 * Math.PI;
const deg = (d) => (d * Math.PI) / 180;

// ---------- Oklab (float, sRGB channels in [0, 1]) ----------

const toLinear = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
const toSrgb = (c) => {
  const x = Math.min(1, Math.max(0, c));
  return x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
};

export function srgbToOklab(r, g, b) {
  const R = toLinear(r), G = toLinear(g), B = toLinear(b);
  const l = Math.cbrt(0.4122214708 * R + 0.5363325363 * G + 0.0514459929 * B);
  const m = Math.cbrt(0.2119034982 * R + 0.6806995451 * G + 0.1073969566 * B);
  const s = Math.cbrt(0.0883024619 * R + 0.2817188376 * G + 0.6299787005 * B);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

export function oklabToSrgb(L, a, b) {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    toSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    toSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    toSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ];
}

const toLch = ([L, a, b]) => [L, Math.hypot(a, b), Math.atan2(b, a)];
const fromLch = (L, C, h) => [L, C * Math.cos(h), C * Math.sin(h)];

// ---------- categories ----------

export const CATEGORIES = [
  { key: "red", label: "Rot", srgb: [205, 30, 40] },
  { key: "orange", label: "Orange", srgb: [240, 130, 30] },
  { key: "yellow", label: "Gelb", srgb: [245, 215, 40] },
  { key: "green", label: "Grün", srgb: [40, 155, 60] },
  { key: "blue", label: "Blau", srgb: [40, 90, 205] },
  { key: "purple", label: "Lila", srgb: [125, 50, 155] },
  { key: "pink", label: "Pink", srgb: [235, 125, 180] },
  { key: "brown", label: "Braun", srgb: [120, 70, 35] },
];
const PROTO = CATEGORIES.map((c) => toLch(srgbToOklab(...c.srgb.map((v) => v / 255))));

const SIGMA_L = 0.16;
const SIGMA_H = 0.3;
const ACH_LOW = 0.025;
const ACH_HIGH = 0.06;
const SKIN_HUE = deg(55);
const SKIN_HUE_INNER = deg(20);
const SKIN_HUE_OUTER = deg(32);
const SKIN_C_INNER = 0.085;
const SKIN_C_OUTER = 0.105;

function smoothstep(e0, e1, x) {
  if (e1 <= e0) return x >= e0 ? 1 : 0;
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}

/** Signed shortest angle h2 - h1 in (-pi, pi], same as Python's modulo. */
function hueDiff(h1, h2) {
  const d = h2 - h1 + Math.PI;
  return d - TAU * Math.floor(d / TAU) - Math.PI;
}

/** Returns {index, probability, chromaticity} for one Oklab LCh colour. */
export function classify([L, C, h]) {
  const logits = PROTO.map(([pL, , ph]) => {
    const dL = (L - pL) / SIGMA_L;
    const dh = hueDiff(h, ph) / SIGMA_H;
    return -0.5 * (dL * dL + dh * dh);
  });
  const max = Math.max(...logits);
  const e = logits.map((v) => Math.exp(v - max));
  const sum = e.reduce((a, b) => a + b, 0);
  let index = 0;
  for (let i = 1; i < e.length; i++) if (e[i] > e[index]) index = i;
  return { index, probability: e[index] / sum, chromaticity: smoothstep(ACH_LOW, ACH_HIGH, C) };
}

export function skinWeight([, C, h]) {
  const inHue = 1 - smoothstep(SKIN_HUE_INNER, SKIN_HUE_OUTER, Math.abs(hueDiff(h, SKIN_HUE)));
  const inChroma = 1 - smoothstep(SKIN_C_INNER, SKIN_C_OUTER, C);
  return inHue * inChroma;
}

// ---------- profile ----------

export function defaultProfile(type = "deutan", severity = 0.5) {
  const s = severity;
  const targets = {
    green: { hue_shift_deg: 20 * s, min_lightness: null },
    purple: { hue_shift_deg: 0, min_lightness: 0.45 + 0.1 * s },
    brown: { hue_shift_deg: 0, min_lightness: 0.38 },
    red:
      type === "protan"
        ? { hue_shift_deg: -6 * s, min_lightness: 0.5 + 0.1 * s }
        : { hue_shift_deg: 0, min_lightness: 0.5 },
  };
  return {
    format: "klarfarbe-profile",
    version: "0.1",
    type,
    severity: s,
    threshold: 0.5,
    strength: 0.85,
    protect_skin: true,
    max_chroma_gain: 2.0,
    targets,
  };
}

// ---------- snapping ----------

function targetsFor(profile) {
  return CATEGORIES.map((c, i) => {
    const t = profile.targets?.[c.key];
    const hue = PROTO[i][2] + deg(t?.hue_shift_deg ?? 0);
    const lMin = t?.min_lightness ?? 0;
    return [lMin, PROTO[i][1], hue];
  });
}

/** Snap one sRGB colour (channels 0-1). Returns {rgb, confidence, category}. */
export function snapColor(r, g, b, profile, _targets = targetsFor(profile)) {
  const lch = toLch(srgbToOklab(r, g, b));
  const { index, probability, chromaticity } = classify(lch);
  const confidence = probability * chromaticity;
  let alpha =
    profile.strength *
    smoothstep(profile.threshold, Math.min(profile.threshold + 0.15, 1), confidence);
  if (profile.protect_skin) alpha *= 1 - skinWeight(lch);

  const [L, C, h] = lch;
  const [lMin, tC, tH] = _targets[index];
  const newH = h + alpha * hueDiff(h, tH);
  const goalC = Math.min(Math.max(C, tC), C * profile.max_chroma_gain);
  const newC = C + alpha * (goalC - C);
  const newL = L + alpha * (Math.max(L, lMin) - L);
  return {
    rgb: oklabToSrgb(...fromLch(newL, newC, newH)),
    confidence,
    category: CATEGORIES[index].key,
  };
}

/** 3D LUT as Uint8Array RGBA, red fastest (WebGL texImage3D layout). */
export function buildLutRGBA(profile, size = 33) {
  const tg = targetsFor(profile);
  const out = new Uint8Array(size * size * size * 4);
  let o = 0;
  for (let bi = 0; bi < size; bi++)
    for (let gi = 0; gi < size; gi++)
      for (let ri = 0; ri < size; ri++) {
        const { rgb } = snapColor(ri / (size - 1), gi / (size - 1), bi / (size - 1), profile, tg);
        out[o++] = Math.round(rgb[0] * 255);
        out[o++] = Math.round(rgb[1] * 255);
        out[o++] = Math.round(rgb[2] * 255);
        out[o++] = 255;
      }
  return out;
}

/** Adobe/Resolve .cube text, red fastest. */
export function buildCube(profile, size = 33, title = "Klarfarbe") {
  const tg = targetsFor(profile);
  const lines = [`TITLE "${title}"`, `LUT_3D_SIZE ${size}`, "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"];
  for (let bi = 0; bi < size; bi++)
    for (let gi = 0; gi < size; gi++)
      for (let ri = 0; ri < size; ri++) {
        const { rgb } = snapColor(ri / (size - 1), gi / (size - 1), bi / (size - 1), profile, tg);
        lines.push(rgb.map((v) => v.toFixed(6)).join(" "));
      }
  return lines.join("\n") + "\n";
}

// ---------- profile test (mirrors python/klarfarbe/profiletest.py) ----------

export const TEST_N_CAPS = 15;
const TEST_L = 0.68;
const TEST_CHROMA = { saturated: 0.1, pale: 0.05 };
const TEST_START_HUE = 25;
const TEST_FAIL_INDEX = 1.6;
const TEST_AXIS = { protan: 9.0, deutan: -3.0 };
const TEST_TYPE_MARGIN = 3.0;

/** Caps for one round: array of 16 sRGB triples (0-1); index 0 is the reference. */
export function testCaps(round) {
  const out = [];
  for (let i = 0; i <= TEST_N_CAPS; i++) {
    const h = deg(TEST_START_HUE + (i * 360) / (TEST_N_CAPS + 1));
    out.push(oklabToSrgb(...fromLch(TEST_L, TEST_CHROMA[round], h)));
  }
  return out;
}

function testMoments(order, caps) {
  const seq = [0, ...order];
  const ab = seq.map((i) => srgbToOklab(...caps[i]).slice(1));
  let a = 0, b = 0, c = 0;
  for (let k = 1; k < ab.length; k++) {
    const du = ab[k][0] - ab[k - 1][0], dv = ab[k][1] - ab[k - 1][1];
    a += du * du; b += du * dv; c += dv * dv;
  }
  const n = ab.length - 1;
  const mid = (a + c) / 2, rad = Math.sqrt(((a - c) / 2) ** 2 + b * b);
  let angle = (0.5 * Math.atan2(2 * b, a - c) * 180) / Math.PI;
  angle = ((((angle + 90) % 180) + 180) % 180) - 90;
  return { angle, major: Math.sqrt((mid + rad) / n), minor: Math.sqrt(Math.max(mid - rad, 0) / n) };
}

/** [confusion index (1 = perfect), axis angle in degrees] for an order of caps 1..15. */
export function confusionIndex(order, round) {
  const caps = testCaps(round);
  const perfect = testMoments(Array.from({ length: TEST_N_CAPS }, (_, i) => i + 1), caps).major;
  const m = testMoments(order, caps);
  return [m.major / perfect, m.angle];
}

/** Profile suggestion from both rounds; same rules as the Python evaluate(). */
export function evaluateTest(orderSaturated, orderPale) {
  const [ciS, angS] = confusionIndex(orderSaturated, "saturated");
  const [ciP, angP] = confusionIndex(orderPale, "pale");
  const base = { index_saturated: ciS, index_pale: ciP };
  if (!(ciS > TEST_FAIL_INDEX)) {
    if (ciP > TEST_FAIL_INDEX)
      return { ...base, type: "unknown", severity: 0.6, angle: angP,
        note: "Mittlere Rot-Grün-Schwäche erkannt. Der Typ lässt sich bei dieser Stärke nicht sicher bestimmen: bitte Protan oder Deutan selbst wählen." };
    return { ...base, type: "unknown", severity: 0.3, angle: null,
      note: "Keine deutliche Verwechslung. Entweder keine oder eine leichte Farbsehschwäche." };
  }
  const dist = (x, y) => { const d = Math.abs(x - y) % 180; return Math.min(d, 180 - d); };
  const dp = dist(angS, TEST_AXIS.protan), dd = dist(angS, TEST_AXIS.deutan);
  if (Math.min(dp, dd) > 30)
    return { ...base, type: "unknown", severity: 0.85, angle: angS,
      note: "Verwechslung erkannt, aber nicht auf der Rot-Grün-Achse. Bitte augenärztlich abklären." };
  if (Math.abs(dp - dd) < TEST_TYPE_MARGIN)
    return { ...base, type: "unknown", severity: 0.85, angle: angS,
      note: "Rot-Grün-Verwechslung erkannt, Typ unsicher. Bitte Protan oder Deutan selbst wählen." };
  return { ...base, type: dp < dd ? "protan" : "deutan", severity: 0.85, angle: angS, note: "" };
}
