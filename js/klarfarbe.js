// Copyright 2026 Mohammad Al-Musawi
// SPDX-License-Identifier: Apache-2.0
//
// Klarfarbe core in plain JavaScript (no dependencies).
// Mirrors python/klarfarbe exactly; the JS tests in python/tests
// (test_js_*.py and the parity tests) check this with node.
// Works in browsers, Node.js and Adobe UXP.

const TAU = 2 * Math.PI;
const deg = (d) => (d * Math.PI) / 180;

/** Default LUT size (same as Python LUT_N). Power of two, as the OpenXR passthrough colour LUT needs. */
export const LUT_N = 64;

/** Purpose statement to show next to any profile test result. */
export const DISCLAIMER =
  "Klarfarbe ist eine Sehhilfe-Software, kein Medizinprodukt und kein Diagnose- oder Eignungstest.";

// ---------- Oklab (float, sRGB channels in [0, 1]) ----------

const toLinear = (c) => {
  const x = Math.min(1, Math.max(0, c));
  return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
};
const toSrgb = (c) => {
  const x = Math.min(1, Math.max(0, c));
  return x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
};

const LAB_TO_LMS = [
  [1.0, 0.3963377774, 0.2158037573],
  [1.0, -0.1055613458, -0.0638541728],
  [1.0, -0.0894841775, -1.291485548],
];
const LMS_TO_RGB = [
  [4.0767416621, -3.3077115913, 0.2309699292],
  [-1.2684380046, 2.6097574011, -0.3413193965],
  [-0.0041960863, -0.7034186147, 1.707614701],
];

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

// ---------- gamut (mirrors oklab.max_chroma) ----------

const GAMUT_BISECT_STEPS = 18;
const GAMUT_NEWTON_STEPS = 3;
const GAMUT_C_HI = 0.5;

function linRgbLch(L, C, u) {
  const q0 = (L + C * u[0]) ** 3, q1 = (L + C * u[1]) ** 3, q2 = (L + C * u[2]) ** 3;
  return LMS_TO_RGB.map((row) => row[0] * q0 + row[1] * q1 + row[2] * q2);
}

/** Largest Oklab chroma inside sRGB at lightness L and hue h (radians). */
export function maxChroma(L, h) {
  const ch = Math.cos(h), sh = Math.sin(h);
  const u = LAB_TO_LMS.map((r) => ch * r[1] + sh * r[2]);
  let lo = 0, hi = GAMUT_C_HI;
  for (let k = 0; k < GAMUT_BISECT_STEPS; k++) {
    const mid = 0.5 * (lo + hi);
    const rgb = linRgbLch(L, mid, u);
    const inside = rgb[0] >= 0 && rgb[1] >= 0 && rgb[2] >= 0 && rgb[0] <= 1 && rgb[1] <= 1 && rgb[2] <= 1;
    if (inside) lo = mid; else hi = mid;
  }
  const rgb = linRgbLch(L, hi, u);
  let chan = 0, best = -Infinity;
  for (let i = 0; i < 3; i++) {
    const v = Math.max(rgb[i] - 1, -rgb[i]);
    if (v > best) { best = v; chan = i; }
  }
  const bound = rgb[chan] > 0.5 ? 1 : 0;
  const row = LMS_TO_RGB[chan];
  let c = hi;
  for (let k = 0; k < GAMUT_NEWTON_STEPS; k++) {
    const m0 = L + c * u[0], m1 = L + c * u[1], m2 = L + c * u[2];
    const f = row[0] * m0 ** 3 + row[1] * m1 ** 3 + row[2] * m2 ** 3 - bound;
    const df = row[0] * 3 * m0 ** 2 * u[0] + row[1] * 3 * m1 ** 2 * u[1] + row[2] * 3 * m2 ** 2 * u[2];
    c -= Math.abs(df) > 1e-12 ? f / df : 0;
  }
  c = Math.min(Math.max(c, lo), hi);
  const greyOk = L >= 0 && L <= 1;
  if (!greyOk) return 0;
  return lo > 0 ? c : lo;
}

// ---------- categories ----------

/** snaps: false = recognised, but never pulled to its prototype (turquoise). */
export const CATEGORIES = [
  { key: "red", label: "Rot", srgb: [205, 30, 40], snaps: true },
  { key: "orange", label: "Orange", srgb: [240, 130, 30], snaps: true },
  { key: "yellow", label: "Gelb", srgb: [245, 215, 40], snaps: true },
  { key: "green", label: "Grün", srgb: [40, 155, 60], snaps: true },
  { key: "blue", label: "Blau", srgb: [40, 90, 205], snaps: true },
  { key: "purple", label: "Lila", srgb: [125, 50, 155], snaps: true },
  { key: "pink", label: "Pink", srgb: [235, 125, 180], snaps: true },
  { key: "brown", label: "Braun", srgb: [120, 70, 35], snaps: true },
  { key: "turquoise", label: "Türkis", srgb: [0, 165, 180], snaps: false },
];
const KEYS = CATEGORIES.map((c) => c.key);
const PROTO = CATEGORIES.map((c) => toLch(srgbToOklab(...c.srgb.map((v) => v / 255))));

const SIGMA_L = 0.16;
const SIGMA_H = 0.3;
const ACH_LOW = 0.02;
const ACH_HIGH = 0.07;
const ACH_DARK_EXTRA = 0.03;
const DARK_RAMP = [0.15, 0.35];
const DARK_FADE = [0.12, 0.26];
const SKIN_HUE = deg(55);
const SKIN_HUE_INNER = deg(20);
const SKIN_HUE_OUTER = deg(30);
const SKIN_C_INNER = 0.105;
const SKIN_C_OUTER = 0.125;
const SKIN_FRINGE_HUE = [deg(30), deg(38)];
const SKIN_FRINGE_C = [0.05, 0.07];

function smoothstep(e0, e1, x) {
  if (e1 <= e0) return x >= e0 ? 1 : 0;
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}

function ramp(e0, e1, x) {
  if (e1 <= e0) return x >= e0 ? 1 : 0;
  return Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
}

/** Signed shortest angle h2 - h1 in (-pi, pi], same as Python's modulo. */
function hueDiff(h1, h2) {
  const d = h2 - h1 + Math.PI;
  return d - TAU * Math.floor(d / TAU) - Math.PI;
}

function chromaticity(L, C) {
  const extra = ACH_DARK_EXTRA * (1 - smoothstep(DARK_RAMP[0], DARK_RAMP[1], L));
  return ramp(ACH_LOW, ACH_HIGH, C - extra) * smoothstep(DARK_FADE[0], DARK_FADE[1], L);
}

/** Returns {index, probability, probabilities, chromaticity} for one Oklab LCh colour. */
export function classify([L, C, h]) {
  const logits = PROTO.map(([pL, , ph]) => {
    const dL = (L - pL) / SIGMA_L;
    const dh = hueDiff(h, ph) / SIGMA_H;
    return -0.5 * (dL * dL + dh * dh);
  });
  const max = Math.max(...logits);
  const e = logits.map((v) => Math.exp(v - max));
  const sum = e.reduce((a, b) => a + b, 0);
  const probabilities = e.map((v) => v / sum);
  let index = 0;
  for (let i = 1; i < e.length; i++) if (e[i] > e[index]) index = i;
  return { index, probability: probabilities[index], probabilities, chromaticity: chromaticity(L, C) };
}

export function skinWeight([, C, h]) {
  const dh = Math.abs(hueDiff(h, SKIN_HUE));
  const core = (1 - smoothstep(SKIN_HUE_INNER, SKIN_HUE_OUTER, dh)) * (1 - smoothstep(SKIN_C_INNER, SKIN_C_OUTER, C));
  const fringe =
    (1 - smoothstep(SKIN_FRINGE_HUE[0], SKIN_FRINGE_HUE[1], dh)) * (1 - smoothstep(SKIN_FRINGE_C[0], SKIN_FRINGE_C[1], C));
  return Math.max(core, fringe);
}

// ---------- profile ----------

export const PROFILE_TYPES = ["protan", "deutan", "unknown"];
export const PROFILE_MODES = ["standard", "elektro"];

const T = (hue_shift_deg = 0, min_lightness = null, min_chroma = null) => ({ hue_shift_deg, min_lightness, min_chroma });

/**
 * Starting profile, same values as Python Profile.default_for.
 * options.mode: "standard" (default) or "elektro" (cable colours after IEC 60445,
 * skin protection off; not a safety function).
 */
export function defaultProfile(type = "deutan", severity = 0.5, options = {}) {
  const mode = options.mode ?? "standard";
  const s = severity;
  const targets = { brown: T(0, 0.38) };
  if (type === "protan") {
    targets.red = T(12.0 * s, 0.5);
    targets.green = T(15.0 * s, 0.62 + 0.08 * s);
    targets.purple = T(-10.0 * s, 0.55 + 0.1 * s);
  } else {
    targets.red = T(0.0, 0.5);
    targets.green = T(60.0 * s ** 3, 0.62 + 0.08 * s);
    targets.purple = T(-10.0 * s, 0.55 + 0.1 * s);
  }
  let protect_skin = true;
  if (mode === "elektro") {
    protect_skin = false;
    targets.brown = T(8.0, 0.4, 0.12);
    targets.blue = T(0, 0.5);
    targets.yellow = T(0, 0.8);
  }
  return validateProfile({
    format: "klarfarbe-profile",
    version: "0.1",
    type,
    severity: s,
    threshold: 0.5,
    strength: 0.85,
    protect_skin,
    max_chroma_gain: 2.0,
    clip_guard: true,
    mode,
    targets,
  });
}

function num(v, name, lo, hi) {
  if (typeof v !== "number" || !Number.isFinite(v)) throw new RangeError(`${name} must be a finite number`);
  if ((lo !== undefined && v < lo) || (hi !== undefined && v > hi))
    throw new RangeError(`${name} must be in [${lo}, ${hi}], got ${v}`);
  return v;
}
const opt = (v, name, lo, hi) => (v === null || v === undefined ? null : num(v, name, lo, hi));
function bool(v, name) {
  if (typeof v !== "boolean") throw new RangeError(`${name} must be true or false`);
  return v;
}

/**
 * Validate a profile object (e.g. parsed JSON) like Python Profile.from_dict.
 * Returns a clean copy with defaults filled in; throws RangeError if invalid.
 * Unknown fields and unknown categories are dropped.
 */
export function validateProfile(data) {
  const isObj = (o) => o !== null && typeof o === "object" && !Array.isArray(o);
  if (!isObj(data)) throw new RangeError("a profile must be a JSON object");
  if (data.format !== "klarfarbe-profile") throw new RangeError("not a klarfarbe profile");
  if (data.version !== undefined && typeof data.version !== "string") throw new RangeError("version must be a string");
  if (!("type" in data) || !("severity" in data)) throw new RangeError("missing field type or severity");
  if (!PROFILE_TYPES.includes(data.type)) throw new RangeError(`type must be one of ${PROFILE_TYPES}`);
  const mode = data.mode ?? "standard";
  if (!PROFILE_MODES.includes(mode)) throw new RangeError(`mode must be one of ${PROFILE_MODES}`);
  const rawTargets = data.targets ?? {};
  if (!isObj(rawTargets)) throw new RangeError("targets must be an object");
  const targets = {};
  for (const [k, t] of Object.entries(rawTargets)) {
    if (!KEYS.includes(k)) continue;
    if (!isObj(t)) throw new RangeError(`targets.${k} must be an object`);
    targets[k] = {
      hue_shift_deg: num(t.hue_shift_deg ?? 0, "hue_shift_deg", -180, 180),
      min_lightness: opt(t.min_lightness, "min_lightness", 0, 1),
      min_chroma: opt(t.min_chroma, "min_chroma", 0, 0.4),
    };
  }
  return {
    format: "klarfarbe-profile",
    version: "0.1",
    type: data.type,
    severity: num(data.severity, "severity", 0, 1),
    threshold: num(data.threshold ?? 0.5, "threshold", 0, 1),
    strength: num(data.strength ?? 0.85, "strength", 0, 1),
    protect_skin: bool(data.protect_skin ?? true, "protect_skin"),
    max_chroma_gain: num(data.max_chroma_gain ?? 2.0, "max_chroma_gain", 1, 4),
    clip_guard: bool(data.clip_guard ?? true, "clip_guard"),
    mode,
    targets,
  };
}

// ---------- snapping (mirrors python/klarfarbe/snap.py) ----------

const CONFIDENCE_WINDOW = 0.3;
const MAX_LIFT = 0.21;
const LIFT_FADE = [0.12, 0.3];
const PROXIMITY = [1.5, 3.0];
const CLIP_FADE = [0.9, 0.995];
const GAMUT_HEADROOM = 0.92;

function targetsFor(profile) {
  return CATEGORIES.map((c, i) => {
    const t = profile.targets?.[c.key];
    const shift = deg(t?.hue_shift_deg ?? 0);
    const lMin = t?.min_lightness ?? 0;
    const cT = t?.min_chroma ?? (c.snaps ? PROTO[i][1] : 0);
    return [lMin, cT, PROTO[i][2] + shift, shift, c.snaps ? 1 : 0];
  });
}

/** Snap one sRGB colour (channels 0-1). Returns {rgb, confidence, category}. */
export function snapColor(r, g, b, profile, _targets = targetsFor(profile)) {
  const lab = srgbToOklab(r, g, b);
  const lch = toLch(lab);
  const [L, C, h] = lch;
  const { index, probabilities: p, chromaticity: chromaW } = classify(lch);

  let near = 0;
  for (let k = 0; k < p.length; k++)
    near += p[k] * (1 - ramp(PROXIMITY[0], PROXIMITY[1], Math.abs(hueDiff(h, PROTO[k][2])) / SIGMA_H));
  let clipW = 1;
  if (profile.clip_guard ?? true) clipW = 1 - ramp(CLIP_FADE[0], CLIP_FADE[1], Math.max(...oklabToSrgb(...lab)));
  const confidence = chromaW * near * clipW;

  let alpha = profile.strength * ramp(profile.threshold, Math.min(profile.threshold + CONFIDENCE_WINDOW, 1), confidence);
  if (profile.protect_skin) alpha *= 1 - skinWeight(lch);

  let dh = 0, goalC = 0, lift = 0;
  for (let k = 0; k < p.length; k++) {
    const [lMin, cT, tH, shift, pull] = _targets[k];
    dh += p[k] * (pull * hueDiff(h, tH) + (1 - pull) * shift);
    goalC += p[k] * Math.min(Math.max(C, cT), C * profile.max_chroma_gain);
    lift += p[k] * Math.min(Math.max(lMin - L, 0), MAX_LIFT);
  }
  lift *= smoothstep(LIFT_FADE[0], LIFT_FADE[1], L);
  const goalH = h + dh;
  const newL = L + alpha * lift;
  const newH = h + alpha * (goalH - h);
  let newC = C;
  if (alpha > 0) {
    const cMax = maxChroma(newL, newH);
    goalC = Math.max(Math.min(goalC, GAMUT_HEADROOM * cMax), C);
    newC = Math.min(C + alpha * (goalC - C), cMax);
  }
  return {
    rgb: oklabToSrgb(...fromLch(newL, newC, newH)),
    confidence,
    category: KEYS[index],
  };
}

function checkSize(size) {
  if (!Number.isInteger(size) || size < 2 || size > 256) throw new RangeError("LUT size must be an integer in [2, 256]");
}

/** 3D LUT as Uint8Array RGBA, red fastest (WebGL texImage3D layout). */
export function buildLutRGBA(profile, size = LUT_N) {
  checkSize(size);
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

/** Adobe/Resolve .cube text, red fastest. Quotes and line breaks in the title are removed. */
export function buildCube(profile, size = LUT_N, title = "Klarfarbe") {
  checkSize(size);
  const tg = targetsFor(profile);
  const safe = (String(title).replace(/"/g, "'").split(/\r\n|\r|\n/)[0] ?? "").replace(/[^\x00-\x7f]/g, "?");
  const lines = [`TITLE "${safe}"`, `LUT_3D_SIZE ${size}`, "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"];
  for (let bi = 0; bi < size; bi++)
    for (let gi = 0; gi < size; gi++)
      for (let ri = 0; ri < size; ri++) {
        const { rgb } = snapColor(ri / (size - 1), gi / (size - 1), bi / (size - 1), profile, tg);
        lines.push(rgb.map((v) => v.toFixed(6)).join(" "));
      }
  return lines.join("\n") + "\n";
}

// ---------- profile test (mirrors python/klarfarbe/profiletest.py) ----------
// Sets software parameters only. Not a diagnostic or fitness test (see DISCLAIMER).

export const TEST_N_CAPS = 15;
const TEST_L = 0.68;
const TEST_CHROMA = { saturated: 0.06, pale: 0.035 };
const TEST_START_HUE = 25;
const TEST_STRONG_INDEX = 2.4;
const TEST_STRONG_COMBINED = 2.6;
const TEST_FAIL_INDEX = 1.9;
const TEST_AXIS = { protan: 8.0, deutan: -3.5 };
const TEST_TYPE_MARGIN = 3.0;
const TEST_MIN_SELECTIVITY = 1.8;

/** Result texts (setting language, no diagnosis). Same as Python profiletest.NOTES. */
export const TEST_NOTES = {
  none:
    "Deine Reihenfolge war nahezu fehlerfrei. Klarfarbe startet mit einer leichten Einstellung. Du kannst sie in der Demo anpassen.",
  moderate:
    "Deine Reihenfolge passt zu einer mittleren Einstellung. Welche Achse besser hilft, ist hier nicht eindeutig: probiere Protan und Deutan in der Demo aus.",
  unsystematic:
    "Deine Reihenfolge wirkt unsystematisch. Bitte wiederhole den Test in Ruhe. Bis dahin startet Klarfarbe mit einer starken Einstellung; welche Achse hilft, wählst du selbst.",
  off_axis:
    "Deine Reihenfolge weicht ab, aber nicht so, wie es bei Rot-Grün-Schwäche typisch ist. Klarfarbe ist dafür womöglich nicht die passende Hilfe. Wenn du dein Farbsehen genau wissen willst, kann das eine Augenarztpraxis prüfen.",
  type_unsure: "Welche Achse besser hilft, ist nicht eindeutig: probiere Protan und Deutan in der Demo aus.",
  typed: "",
};

/** Caps for one round: array of 16 sRGB triples (0-1); index 0 is the reference. */
export function testCaps(round) {
  const out = [];
  for (let i = 0; i <= TEST_N_CAPS; i++) {
    const h = deg(TEST_START_HUE + (i * 360) / (TEST_N_CAPS + 1));
    out.push(oklabToSrgb(...fromLch(TEST_L, TEST_CHROMA[round], h)));
  }
  return out;
}

/** Throws RangeError unless order is a permutation of 1..15. */
export function validateOrder(order) {
  if (!Array.isArray(order) || order.length !== TEST_N_CAPS) throw new RangeError("order must contain each cap 1..15 exactly once");
  const seen = new Set(order);
  for (let i = 1; i <= TEST_N_CAPS; i++)
    if (!seen.has(i)) throw new RangeError("order must contain each cap 1..15 exactly once");
  return order;
}

function testScatter(order, caps) {
  const seq = [0, ...order];
  const ab = seq.map((i) => srgbToOklab(...caps[i]).slice(1));
  let a = 0, b = 0, c = 0;
  for (let k = 1; k < ab.length; k++) {
    const du = ab[k][0] - ab[k - 1][0], dv = ab[k][1] - ab[k - 1][1];
    a += du * du; b += du * dv; c += dv * dv;
  }
  return { a, b, c, n: ab.length - 1 };
}

function testMoments(order, caps) {
  const { a, b, c, n } = testScatter(order, caps);
  const mid = (a + c) / 2, rad = Math.sqrt(((a - c) / 2) ** 2 + b * b);
  let angle = (0.5 * Math.atan2(2 * b, a - c) * 180) / Math.PI;
  angle = ((((angle + 90) % 180) + 180) % 180) - 90;
  return { angle, major: Math.sqrt((mid + rad) / n), minor: Math.sqrt(Math.max(mid - rad, 0) / n) };
}

const perfectOrder = () => Array.from({ length: TEST_N_CAPS }, (_, i) => i + 1);

/** [confusion index (1 = perfect), axis angle in degrees] for an order of caps 1..15. */
export function confusionIndex(order, round) {
  validateOrder(order);
  const caps = testCaps(round);
  const perfect = testMoments(perfectOrder(), caps).major;
  const m = testMoments(order, caps);
  return [m.major / perfect, m.angle];
}

/** Selectivity S = major / minor radius; random orders give S near 1. */
export function testSelectivity(order, round) {
  validateOrder(order);
  const m = testMoments(order, testCaps(round));
  return m.major / Math.max(m.minor, 1e-12);
}

/** Confusion axis from both rounds together (normalised scatter matrices summed). */
export function combinedAxis(orderSaturated, orderPale) {
  let A = 0, B = 0, Cc = 0;
  for (const [order, round] of [[orderSaturated, "saturated"], [orderPale, "pale"]]) {
    validateOrder(order);
    const caps = testCaps(round);
    const p = testMoments(perfectOrder(), caps).major;
    const s = testScatter(order, caps);
    const k = s.n * p * p;
    A += s.a / k; B += s.b / k; Cc += s.c / k;
  }
  const angle = 0.5 * (Math.atan2(2 * B, A - Cc) * 180) / Math.PI;
  return ((((angle + 90) % 180) + 180) % 180) - 90;
}

/**
 * Suggested starting setting from both rounds; same rules as Python evaluate().
 * Returns {type, severity, angle, index_saturated, index_pale, selectivity, note_key, note}.
 * Throws RangeError for an invalid order.
 */
export function evaluateTest(orderSaturated, orderPale) {
  const [ciS, angS] = confusionIndex(orderSaturated, "saturated");
  const [ciP, angP] = confusionIndex(orderPale, "pale");
  const sel = testSelectivity(orderSaturated, "saturated");
  const base = { index_saturated: ciS, index_pale: ciP, selectivity: sel };
  const result = (type, severity, angle, key) => ({ ...base, type, severity, angle, note_key: key, note: TEST_NOTES[key] });
  const comb = Math.sqrt(ciS * ciP);
  if (!(ciS > TEST_STRONG_INDEX || comb > TEST_STRONG_COMBINED)) {
    if (comb > TEST_FAIL_INDEX) return result("unknown", 0.6, angP, "moderate");
    return result("unknown", 0.3, null, "none");
  }
  if (sel < TEST_MIN_SELECTIVITY) return result("unknown", 0.85, angS, "unsystematic");
  const angle = combinedAxis(orderSaturated, orderPale);
  const dist = (x, y) => { const d = Math.abs(x - y) % 180; return Math.min(d, 180 - d); };
  const dp = dist(angle, TEST_AXIS.protan), dd = dist(angle, TEST_AXIS.deutan);
  if (Math.min(dp, dd) > 30) return result("unknown", 0.85, angle, "off_axis");
  if (Math.abs(dp - dd) < TEST_TYPE_MARGIN) return result("unknown", 0.85, angle, "type_unsure");
  return result(dp < dd ? "protan" : "deutan", 0.85, angle, "typed");
}
