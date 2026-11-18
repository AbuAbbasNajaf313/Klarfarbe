# Klarfarbe

**Open library for personal colour assistance for people with red-green colour vision deficiency.**
**Offene Bibliothek für persönliche Farbhilfe bei Rot-Grün-Schwäche.**

![Vorher/Nachher](docs/vorher-nachher.png)

## Worum es geht

Etwa acht Prozent der Männer sehen Farben eingeschränkt, meist auf der Rot-Grün-Achse. Bestehende Hilfen färben das ganze Bild um oder benennen nur Farben. Klarfarbe geht anders vor:

1. **Ein persönliches Profil** beschreibt Typ (Protan, Deutan) und Stärke der Farbsehschwäche.
2. **Ein Kategorie-Modell** ordnet jedem Farbwert eine Grundfarbe mit Sicherheitswert zu, auch wenn die Farbe gedeckt ist.
3. **Gezieltes Einrasten:** Nur eindeutig erkannte Farben werden auf einen Ton gezogen, den die Person sicher unterscheidet. Ein gedecktes Rot wird klar rot, eine dunkle Aubergine wird erkennbar lila.
4. **Totzone:** Unsichere Farben sowie Grau, Schwarz und Weiß bleiben unverändert. Klarfarbe täuscht keine Sicherheit vor.
5. **Hautton-Schutz:** Hauttöne aller Schattierungen bleiben im Alltagsmodus unverändert. Im Handwerksmodus (`--handwerk`) ist der Schutz aus, damit z. B. braune Adern deutlicher werden.

Klarfarbe ist eine **Hilfe zur Farbunterscheidung**. Es ersetzt keine Prüfung und keine Sicherheitsmessung, etwa beim Arbeiten an elektrischen Anlagen.

## Schnellstart (macOS, Linux, Windows)

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Live-Webcam: links Original, rechts Klarfarbe
python demo_webcam.py --type deutan --severity 0.6

# Ein Foto umwandeln
python -m klarfarbe.cli image foto.jpg foto_klar.jpg --type deutan

# LUT für Premiere, DaVinci Resolve, OBS exportieren
python -m klarfarbe.cli cube klarfarbe_deutan.cube --type deutan

# Tests
pip install pytest && python -m pytest tests
```

Tasten in der Webcam-Demo: `q` beenden, `v` Ansicht wechseln, `h` Hautton-Schutz an/aus, `t` Protan/Deutan, `+`/`-` Sicherheitsschwelle.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `python/klarfarbe/oklab.py` | sRGB ↔ Oklab, vektorisiert |
| `python/klarfarbe/categories.py` | Kategorie-Modell mit Sicherheitswert, Hautton-Erkennung |
| `python/klarfarbe/snap.py` | Einrasten, 3D-LUT, `.cube`-Export |
| `python/klarfarbe/profile.py` | Profilformat lesen und schreiben |
| `spec/profile-format.md` | Offene Spezifikation des Profilformats |
| `js/oklab.js` | Oklab-Umrechnung für Browser und Adobe-UXP |

## Stand und Plan

Version 0.1 ist ein lauffähiger Prototyp. Geplant (siehe Prototype-Fund-Antrag): Profiltest nach dem Prinzip des Farnsworth-Munsell-100-Tests, gelerntes Farbnamen-Modell, Shader in GLSL, WGSL und Metal, Browser-Erweiterung, iOS-Kamera-App, Unity-Paket für Passthrough auf der Meta Quest 3, Nutzertests mit Betroffenen.

## Lizenz

Apache-2.0, siehe [LICENSE](LICENSE). Copyright 2026 Mohammad Al-Musawi.
