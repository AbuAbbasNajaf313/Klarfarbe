// Copyright 2026 Mohammad Al-Musawi
// SPDX-License-Identifier: Apache-2.0
//
// sRGB <-> Oklab for browsers and Adobe UXP plugins.
// Taken from the AuraColor prototype (shared/color-math.js).
// Matrices from Björn Ottosson: https://bottosson.github.io/posts/oklab/

/** sRGB channel 0-255 -> linear 0-1 */
export function srgbToLinear(c) {
  const s = c / 255.0;
  return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
}

/** linear 0-1 -> sRGB channel 0-255 (rounded, clipped) */
export function linearToSrgb(c) {
  const s = c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1.0 / 2.4) - 0.055;
  return Math.max(0, Math.min(255, Math.round(s * 255))) + 0;
}

/** linear RGB 0-1 -> Oklab {L, a, b} */
export function linearRgbToOklab(r, g, b) {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return {
    L: 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    a: 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    b: 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  };
}

/** Oklab -> linear RGB 0-1 (not clipped) */
export function oklabToLinearRgb(L, a, b) {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return {
    r: 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    g: -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    b: -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  };
}

/** sRGB 0-255 -> Oklab */
export function srgbToOklab(r, g, b) {
  return linearRgbToOklab(srgbToLinear(r), srgbToLinear(g), srgbToLinear(b));
}

/** Oklab -> sRGB 0-255 */
export function oklabToSrgb(L, a, b) {
  const lin = oklabToLinearRgb(L, a, b);
  return { r: linearToSrgb(lin.r), g: linearToSrgb(lin.g), b: linearToSrgb(lin.b) };
}
