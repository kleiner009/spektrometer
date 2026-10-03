# Hardware

## Druckdateien (`druckdateien/`)

| Datei | Inhalt |
|---|---|
| `*.3mf` | druckfertige Teile (Grundplatte, Halter, Verbinder, Abschlussblenden, Spaltkappe) |
| `*.f3d` | Fusion-360-Konstruktion (parametrisch, zum Anpassen) |

**Druckeinstellungen:** PETG schwarz matt, Schichthöhe 0,2 mm, mindestens 3 Wände, Füllung ≥ 30 % (Halter ≥ 40 % um die Gewindeeinsätze). Grundplatte **mit der Unterseite aufs Bett** drucken: Senkungen und Taschen brauchen dann keine Stützen. Elefantenfuß kompensieren.

## Raster-Grundplatten-System RGS (`rgs/`)

Alle Bauteile sitzen in eigenen, von unten verschraubten Haltern auf einer Rasterplatte. Ein Bauteilwechsel (z. B. andere Kamera) kostet dadurch nur einen neuen Halter, nicht die ganze Platte.

| Merkmal | Wert |
|---|---|
| Raster | 12,5 mm, erster Punkt 6,25 mm vom Rand |
| Platten | 125 × 125 und 125 × 250 mm, 6 mm dick |
| Befestigung | Kreuzloch an jedem Rasterpunkt, M3 × 10 Senkkopf (ISO 10642) von unten in M3-Gewindeeinsätze im Halter |
| Justierweg | ±2,5 mm je Achse, Drehung ≈ ±10° bei zwei Schrauben |
| Verbindung | lose Doppel-Schwalbenschwänze in Taschen von unten (Spalten/Zeilen C und H), Abschlussblenden für gerade Kanten |
| Optische Achse | 30 mm über der Plattenoberseite |

- **[RGS_v1.0_Zeichnungen.pdf](rgs/RGS_v1.0_Zeichnungen.pdf):** technische Zeichnungen mit allen Maßen und Toleranzen (A3, 2 Blätter)
- **[rgs_zeichnung.py](rgs/rgs_zeichnung.py):** erzeugt die Zeichnungen aus den Parametern, nach Maßänderungen neu ausführen

Die Schraube rutscht auch in der Kreuzmitte nicht durch: Der Kopf liegt dort an den vier inneren Ecken auf (0,75–1,35 mm versenkt) und zentriert sich selbst. Nur handfest anziehen.
