# Klarfarbe

**Open library for personal colour assistance for people with red-green colour vision deficiency.**
**Offene Bibliothek für persönliche Farbhilfe bei Rot-Grün-Schwäche.**

![Vorher/Nachher](docs/vorher-nachher.png)

## Worum es geht

In Europa sehen etwa acht Prozent der Männer Farben eingeschränkt, meist auf der Rot-Grün-Achse. Bestehende Hilfen färben das ganze Bild um oder benennen nur Farben. Klarfarbe geht anders vor:

1. **Ein persönliches Profil** beschreibt Typ (Protan, Deutan) und Stärke der Farbsehschwäche.
2. **Ein Kategorie-Modell** ordnet jedem Farbwert Grundfarben mit einem Zuordnungswert zu, auch wenn die Farbe gedeckt ist. Der Zuordnungswert ist eine Modellgröße, keine geprüfte Wahrscheinlichkeit.
3. **Gezieltes Einrasten:** Deutlich farbige Farben werden zu Tönen verschoben, die sich für die Person besser unterscheiden. Das Ziel ist eine nach Wahrscheinlichkeit gewichtete Mischung der Kategorie-Ziele, deshalb gibt es keine harten Sprünge an Kategoriegrenzen. Ein gedecktes Rot wird kräftiger, eine dunkle Aubergine heller.
4. **Totzone:** Grau, Schwarz, Weiß, sehr dunkle Pixel (dort ist der Farbton meist nur Rauschen), überbelichtete Pixel und Türkis/Petrol bleiben unverändert. Sättigung und Helligkeit werden nur erhöht; nur wo sRGB den neuen Farbton nicht so satt darstellen kann, wird die Sättigung bei gleicher Helligkeit und gleichem Farbton an den Farbraumrand gesetzt.
5. **Hautton-Schutz:** Hauttöne bleiben im Standardmodus unverändert. Der Schutz ist ein Farbband, kein Hautdetektor: Er schützt auch Holz, Karton und viele Brauntöne.
6. **Modus Elektro** (`--elektro`, Profilfeld `"mode": "elektro"`): Hautton-Schutz aus, die Aderfarben nach IEC 60445 (braun, schwarz, grau, blau, grün-gelb) werden stärker getrennt.

Die Zieltöne sind mit simulierten Betrachtern (Machado et al. 2009, Viénot et al. 1999) so gewählt, dass kritische Farbpaare (Rot–Grün, Rot–Grau, Grün–Grau, schlechtestes Kategorie-Paar) für Protan und Deutan weiter auseinanderliegen als ohne Klarfarbe. `python/tests/test_benefit.py` prüft das. Das sind Modellwerte, keine Ergebnisse von Nutzertests.

## Zweck und Grenzen

Klarfarbe ist eine Sehhilfe-Software, kein Medizinprodukt und kein Diagnose- oder Eignungstest. Es passt die Darstellung von Bildinhalten an und hilft, Farben leichter zu unterscheiden.

- **Keine Sicherheitsfunktion.** Nicht für den Straßenverkehr, Ampeln oder andere Signallichter verwenden: Überbelichtete rote und gelbe LEDs sehen für die Kamera gleich aus. Bei elektrischen Arbeiten Leitungen immer mit Prüfgerät prüfen, auch im Modus Elektro.
- **Keine Lebensmittelprüfung.** Ob Fleisch durchgegart ist, lässt sich an der Farbe nicht verlässlich erkennen; dafür ein Thermometer verwenden.
- **Keine Berufseignung.** Klarfarbe ersetzt keine Farbsehtauglichkeit und darf in Eignungsuntersuchungen nicht verwendet werden.
- **Der Profiltest** stellt nur Software-Parameter ein. Er ersetzt keine augenärztliche Untersuchung.
- **Kamerabilder** hängen von Weißabgleich, Belichtung und Licht ab. Unter Kunstlicht oder bei starker Über- oder Unterbelichtung kann eine Farbe falsch eingeordnet werden.
- Klarfarbe-LUTs nicht hintereinanderschalten (z. B. in OBS und danach im Schnittprogramm): Die Wirkung verstärkt sich.

## Browser-Demo

`web/index.html` ist eine eigenständige Seite: Testbild, eigene Fotos oder Kamera, Vergleich per Trennlinie, Export als Profil und `.cube`. Die Farbumrechnung läuft als WebGL2-Shader mit einer 3D-Nachschlagetabelle (64³).

```bash
python3 -m http.server 8000   # im Hauptordner des Repos
# dann http://localhost:8000/web/ öffnen (Kamera funktioniert nur über http://localhost oder https)
```

### Tragbar ausprobieren

- **Smartphone mit Pappbrille** (z. B. Google-Cardboard-Halterung): Demo über GitHub Pages auf dem Handy öffnen, **Pappbrille** wählen, Handy quer einstecken. Klarfarbe läuft dann auf der Rückkamera, für beide Augen. Experimentell; nur kurz und im Sitzen verwenden.
- **Meta Quest 3/3S (Experiment):** In aktuellen Versionen des Quest-Browsers sind die Passthrough-Kameras nach Freigabe der Berechtigung „Headset-Kameras“ als normale Kameras erreichbar („camera 1, facing back“ = links). Demo im Quest-Browser öffnen, **Kamera** wählen, dann **Quest-Rundumsicht**. Die Seite zeigt ein Kamerabild für beide Augen (kein Stereo, keine Reprojektion, spürbare Verzögerung), auf echter Hardware noch nicht getestet. Nicht im Gehen oder an Maschinen benutzen.
- Antippen oder `Esc` beendet den Modus. Die Kamera funktioniert nur über `https://` oder `http://localhost`.

**Ausblick Quest:** Der bessere Weg ist die native Passthrough-Farbtabelle von OpenXR (`XR_META_passthrough_color_lut`). Sie wendet eine 3D-LUT direkt im Passthrough des Headsets an, mit Stereo, Reprojektion und der normalen Passthrough-Latenz. Die Klarfarbe-LUT hat dafür schon die passende Größe (64, eine Zweierpotenz).

Mit GitHub Pages (Settings → Pages → Branch `main`, Ordner `/ (root)`) ist die Demo öffentlich unter `https://<name>.github.io/Klarfarbe/web/` erreichbar. Nach Änderungen an `js/klarfarbe.js` oder `web/template.html`: `python3 web/build.py`.

## Schnellstart (macOS, Linux, Windows)

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Live-Webcam: links Original, rechts Klarfarbe
python demo_webcam.py --type deutan --severity 0.6

# Ein Foto umwandeln
python -m klarfarbe.cli image foto.jpg foto_klar.jpg --type deutan

# Modus Elektro (Aderfarben, Hautton-Schutz aus; keine Sicherheitsfunktion)
python -m klarfarbe.cli image kabel.jpg kabel_klar.jpg --type deutan --elektro

# LUT für Premiere, DaVinci Resolve, OBS exportieren (Standardgröße 64, --lut-size 2-256)
python -m klarfarbe.cli cube klarfarbe_deutan.cube --type deutan

# Tests (224, inklusive Abgleich Python ↔ JavaScript, braucht Node.js)
pip install pytest && python -m pytest tests
```

Nach `pip install .` im Ordner `python` steht der Befehl auch als `klarfarbe` zur Verfügung. `--handwerk` ist der alte Name von `--elektro` und funktioniert weiter.

Tasten in der Webcam-Demo: `q` beenden, `v` Ansicht wechseln, `h` Hautton-Schutz an/aus, `t` Protan/Deutan, `+`/`-` Schwelle.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `python/klarfarbe/oklab.py` | sRGB ↔ Oklab, vektorisiert; Farbraumrand `max_chroma(L, h)` |
| `python/klarfarbe/categories.py` | Kategorie-Modell mit Zuordnungswert, Hautton-Band |
| `python/klarfarbe/snap.py` | Einrasten, 3D-LUT (`LUT_N = 64`), `.cube`-Export |
| `python/klarfarbe/profile.py` | Profilformat lesen, prüfen und schreiben |
| `python/klarfarbe/profiletest.py` | Profiltest (D-15-Prinzip), Auswertung nach Vingrys & King-Smith, Kalibrierung mit simulierten Betrachtern |
| `spec/profile-format.md` | Offene Spezifikation des Profilformats |
| `js/oklab.js` | Oklab-Umrechnung für Browser und Adobe-UXP |
| `js/klarfarbe.js` | Kompletter Kern in JavaScript, ergebnisgleich mit Python (automatisch getestet) |
| `web/` | Browser-Demo mit WebGL2-Shader |

## Profiltest

Zwei Runden Farben ordnen (kräftig, dann blass), Prinzip des Farnsworth-D-15. Die kräftige Runde hat etwa die Farbabstände des D-15, die blasse liegt zwischen D-15 und dem entsättigten D-15d. Die Auswertung nach Vingrys und King-Smith (1988) liefert einen Verwechslungsindex (1,00 = Kreisfolge), eine Verwechslungsachse und den Selektivitätsindex (zufällige Reihenfolgen liegen nahe 1).

- **Starke Einstellung:** Verwechslungsindex der kräftigen Runde über 2,4 (oder beider Runden zusammen über 2,6). Ein Vorschlag Protan oder Deutan kommt nur, wenn die Reihenfolge systematisch ist (Selektivität mindestens 1,8) und die Achse aus beiden Runden klar näher an einer der Achsen liegt (Protan etwa +8°, Deutan etwa −3,5° in Oklab a/b). Sonst wählt die Person selbst.
- **Mittlere Einstellung:** beide Runden zusammen (geometrisches Mittel) über 1,9. Den Typ schlägt der Test hier nicht vor.
- **Leichte Einstellung:** sonst.
- Eine Reihenfolge, die nicht jede Kappe genau einmal enthält, wird abgelehnt.

Die Grenzwerte sind mit simulierten Betrachtern kalibriert (`profiletest.calibrate()`). In der Simulation stufen sie Normalsichtige bei angenommenem Wahrnehmungsrauschen nie und bei 1,7-fachem Rauschen in etwa 8 % als „mittel“ ein; zufälliges Klicken ergibt in unter 1 % einen Typ. Das sind Modellwerte, keine Normdaten. Der Test läuft auf unkalibrierten Bildschirmen und liefert nur einen Startwert, den die Person selbst nachstellt. Vor dem Test Night Shift, True Tone und Blaulichtfilter ausschalten.

## Stand und Plan

Version 0.2 ist ein lauffähiger Prototyp. Geplant: Validierung des Profiltests mit Betroffenen, gelerntes Farbnamen-Modell, Weißabgleich per Graukarte, Shader in GLSL, WGSL und Metal, Browser-Erweiterung, Export für die OpenXR-Passthrough-Farbtabelle, Nutzertests mit Betroffenen.

## Lizenz

Apache-2.0, siehe [LICENSE](LICENSE). Copyright 2026 Mohammad Al-Musawi.
