# Klarfarbe-Profilformat, Version 0.1

Ein Profil beschreibt, wie eine Person Farben wahrnimmt und wie Klarfarbe für sie einrasten soll. Das Format ist JSON, offen und unabhängig von einer bestimmten App. Jede Anwendung, die dieses Format liest, kann dieselbe persönliche Einstellung verwenden.

## Beispiel (Auszug)

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
  "targets": {
    "green":  { "hue_shift_deg": 12.0, "min_lightness": null },
    "red":    { "hue_shift_deg": 0.0,  "min_lightness": 0.5 },
    "purple": { "hue_shift_deg": 0.0,  "min_lightness": 0.51 }
  }
}
```

## Felder

| Feld | Typ | Pflicht | Bedeutung |
| --- | --- | --- | --- |
| `format` | String | ja | immer `klarfarbe-profile` |
| `version` | String | ja | Version dieses Formats, derzeit `0.1` |
| `type` | `protan` \| `deutan` \| `unknown` | ja | Art der Farbsehschwäche |
| `severity` | Zahl 0–1 | ja | Stärke: 0 leicht, 1 stark |
| `threshold` | Zahl 0–1 | nein, 0.5 | Mindestsicherheit, ab der eingerastet wird |
| `strength` | Zahl 0–1 | nein, 0.85 | Wie weit eine sichere Farbe zum Ziel wandert |
| `protect_skin` | Boolean | nein, true | Hauttöne und ähnliche Brauntöne unverändert lassen |
| `max_chroma_gain` | Zahl ≥ 1 | nein, 2.0 | Höchstens so viel mehr Sättigung |
| `targets` | Objekt | nein | Anpassungen je Kategorie, siehe unten |

Kategorien in `targets`: `red`, `orange`, `yellow`, `green`, `blue`, `purple`, `pink`, `brown`.

| Feld in `targets.<kategorie>` | Typ | Bedeutung |
| --- | --- | --- |
| `hue_shift_deg` | Zahl | dreht den Ziel-Farbton (Oklab, Grad) |
| `min_lightness` | Zahl 0–1 oder `null` | hebt dunkle Farben dieser Kategorie mindestens auf diese Helligkeit (Oklab L) |

## Regeln

- Grau, Schwarz und Weiß werden nie verändert.
- Farben unter `threshold` werden nicht verändert.
- Sättigung und Helligkeit werden nur erhöht, nie verringert.
- Leser müssen unbekannte Felder ignorieren, damit ältere Programme neuere Profile lesen können.

## Geplant

Version 0.2 ergänzt die Rohdaten des Profiltests (Fehler je Farbachse), damit Anwendungen eigene Ziele berechnen können.
