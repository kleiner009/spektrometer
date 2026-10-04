# Hardware

## Druckdateien (`druckdateien/`)

| Datei | Inhalt |
|---|---|
| `Spektrometer_01-Grundplatte.3mf` | Grundplatte, trägt alle Halter |
| `Spektrometer_01-Halter-Spektroskop.3mf` | Halter für das Taschenspektroskop |
| `Spektrometer_01-Kamerahalter.3mf` | Halter für die Kamera OV9281 mit M12-Objektiv |
| `Spektrometer_01-RasPi-Halter.3mf` | Halter für den Raspberry Pi 5 mit Display |
| `Spektrometer_01-Spaltkappe.3mf` | Spaltkappe mit Aufnahme für die Streuscheibe |
| `Spektrometer_01-Tunnel.3mf` | Lichttunnel zwischen Lampe und Spaltkappe |
| `Spektrometer_01_All.3mf` | alle Teile zusammen auf einer Druckplatte |
| `Spektrometer_01-All.f3d` | Fusion-360-Konstruktion aller Teile (zum Anpassen, z. B. für eine andere Kamera) |

## Stückliste Kleinteile

| Teil | Anzahl |
|---|---|
| Gewindeeinsatz M3 (z. B. ruthex RX-M3x5.7) | 9 |
| Gewindeeinsatz M2 (z. B. ruthex RX-M2x4) | 8 |
| Senkkopfschraube M3 × 10, Innensechskant | 8 |
| Linsen-/Pilzkopfschraube M3 × 12, Innensechskant | 1 |
| Linsenkopfschraube M2 × 10, Innensechskant | 8 |

Die Gewindeeinsätze werden mit dem Lötkolben eingeschmolzen. Bezugsquellen siehe [KAUFLISTE.md](../KAUFLISTE.md).

**Druckeinstellungen:** PETG schwarz matt (wärmefest wegen der Glühlampe, streulichtarm), Schichthöhe 0,2 mm, mindestens 3 Wände, Füllung ≥ 30 %.

## Hinweise zum Aufbau

- **Streuscheibe vor dem Spalt ist Pflicht.** Ohne sie hängen Helligkeit und Lage des Spektrums stark von der Lampenposition ab.
- **Kamera mittig und dicht vor das Okular** setzen und auf das Spektrum scharfstellen.
- **Kamerakabel zugentlasten.** Ein gelöstes Flachbandkabel zeigt sich als „Camera frontend has timed out“.
- **Streulicht vermeiden:** Fällt Licht am Spektroskop vorbei auf die Kamera, erscheint im Bild ein heller Fleck neben dem Spektrum und verfälscht die Messung. Übergang Spektroskop → Kamera abdunkeln.
