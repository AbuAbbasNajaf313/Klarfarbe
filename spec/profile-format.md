# Klarfarbe-Profilformat, Version 0.1

Ein Profil beschreibt, wie eine Person Farben wahrnimmt und wie Klarfarbe für sie einrasten soll. Das Format ist JSON, offen und unabhängig von einer bestimmten App. Jede Anwendung, die dieses Format liest, kann dieselbe persönliche Einstellung verwenden.

Ein Profil enthält Software-Parameter, keine Diagnose. Weil `type` und `severity` Rückschlüsse auf das Farbsehen zulassen, sollen Anwendungen Profile nur lokal speichern und nur mit ausdrücklicher Zustimmung weitergeben.

## Beispiel

```json
{
  "format": "klarfarbe-profile",
  "version": "0.1",
  "type": "deutan",
  "severity": 0.6,
  "threshold": 0.5,
  "strength": 0.85,
  "protect_skin": true,
  "max_chroma_gain": 2.0,
  "clip_guard": true,
  "mode": "standard",
  "targets": {
    "brown":  { "hue_shift_deg": 0.0,   "min_lightness": 0.38, "min_chroma": null },
    "red":    { "hue_shift_deg": 0.0,   "min_lightness": 0.5,  "min_chroma": null },
    "green":  { "hue_shift_deg": 12.96, "min_lightness": 0.668, "min_chroma": null },
    "purple": { "hue_shift_deg": -6.0,  "min_lightness": 0.61, "min_chroma": null }
  }
}
```

## Felder

| Feld | Typ | Pflicht | Bedeutung |
| --- | --- | --- | --- |
| `format` | String | ja | immer `klarfarbe-profile` |
| `version` | String | nein, `0.1` | Version dieses Formats |
| `type` | `protan` \| `deutan` \| `unknown` | ja | Achse der Farbhilfe; `unknown` verhält sich wie `deutan`, bis die Person wählt |
| `severity` | Zahl 0–1 | ja | Stärke: 0 leicht, 1 stark |
| `threshold` | Zahl 0–1 | nein, 0.5 | Mindest-Zuordnungswert, ab dem eingerastet wird |
| `strength` | Zahl 0–1 | nein, 0.85 | Wie weit eine sichere Farbe zum Ziel wandert |
| `protect_skin` | Boolean | nein, `true` | Hauttöne und ähnliche Brauntöne unverändert lassen |
| `max_chroma_gain` | Zahl 1–4 | nein, 2.0 | Höchstens so viel mehr Sättigung |
| `clip_guard` | Boolean | nein, `true` | Überbelichtete Pixel (ein Kanal nahe 255) nicht einrasten. Für Kamerabilder an lassen, für Grafiken und Bildschirmfotos ausschalten |
| `mode` | `standard` \| `elektro` | nein, `standard` | Voreinstellung, aus der das Profil entstanden ist. `elektro`: Aderfarben nach IEC 60445 stärker getrennt, `protect_skin` aus. Keine Sicherheitsfunktion |
| `targets` | Objekt | nein | Anpassungen je Kategorie, siehe unten |

Kategorien in `targets`: `red`, `orange`, `yellow`, `green`, `blue`, `purple`, `pink`, `brown`, `turquoise`.
`turquoise` (Türkis/Petrol) wird erkannt, aber nicht zu einem Prototyp gezogen; dort wirken nur ausdrücklich gesetzte Werte.

| Feld in `targets.<kategorie>` | Typ | Bedeutung |
| --- | --- | --- |
| `hue_shift_deg` | Zahl −180 bis 180, Standard 0 | dreht den Ziel-Farbton (Oklab, Grad) |
| `min_lightness` | Zahl 0–1 oder `null` | hebt dunkle Farben dieser Kategorie in Richtung dieser Helligkeit (Oklab L), höchstens um 0,21 je Anwendung |
| `min_chroma` | Zahl 0–0.4 oder `null` | Ziel-Sättigung (Oklab C) statt der des Prototyps |

## Prüfung beim Lesen

Leser müssen ein Profil so prüfen (Referenz: `Profile.from_dict` in Python, `validateProfile` in JavaScript):

- Die Wurzel ist ein Objekt, `format` ist `klarfarbe-profile`, `type` und `severity` sind vorhanden.
- Zahlen sind endlich (kein `NaN`, kein `Infinity`) und liegen in den Bereichen der Tabellen oben. Booleans sind echte JSON-Booleans, keine Strings wie `"false"`.
- `targets` und jedes `targets.<kategorie>` sind Objekte.
- Unbekannte Felder und unbekannte Kategorien werden ignoriert, damit ältere Programme neuere Profile lesen können. Das gilt auch für eine höhere `version`.
- Jeder andere Fehler führt zur Ablehnung des ganzen Profils (Python: `ValueError`, JavaScript: `RangeError`).
- Schreiber dürfen kein `NaN` oder `Infinity` ausgeben.

## Regeln für das Einrasten

- Grau, Schwarz und Weiß werden nie verändert. Sehr dunkle Pixel (Oklab L unter etwa 0,12) gelten als unbunt, weil ihr Farbton meist Rauschen ist; dunkle Farben brauchen mehr Sättigung, um als bunt zu gelten.
- Farben mit einem Zuordnungswert unter `threshold` werden nicht verändert. Darüber steigt die Wirkung über ein Fenster von 0,3 linear an.
- Das Ziel einer Farbe ist die nach Kategorie-Wahrscheinlichkeit gewichtete Mischung der Kategorie-Ziele (Farbton zirkulär um den Eingangsfarbton gemittelt). Kleine Eingabeänderungen ergeben deshalb kleine Ausgabeänderungen.
- Helligkeit wird nur erhöht. Sättigung wird nur erhöht, außer wo sRGB den neuen Farbton bei dieser Helligkeit nicht so satt darstellen kann; dann wird die Sättigung bei gleicher Helligkeit und gleichem Farbton auf den Farbraumrand gesetzt (kein kanalweises Abschneiden). Ziel-Sättigungen bleiben 8 % unter dem Rand.
- Die Werte des Zuordnungsmodells sind Modellgrößen, keine geprüften Wahrscheinlichkeiten.

## Geplant

Eine spätere Version ergänzt die Rohdaten des Profiltests (Fehler je Farbachse), damit Anwendungen eigene Ziele berechnen können.
