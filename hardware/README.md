# Hardware

## Druckdateien (`druckdateien/`)

| Datei | Inhalt |
|---|---|
| `*.3mf` | druckfertige Teile (Grundplatte, Halter, Spaltkappe mit Streuscheibe und Lichttunnel) |
| `*.f3d` | Fusion-360-Konstruktion (zum Anpassen, z. B. für eine andere Kamera) |

Die Dateien und eine Stückliste der Kleinteile (Schrauben, Gewindeeinsätze) folgen.

**Druckeinstellungen:** PETG schwarz matt (wärmefest wegen der Glühlampe, streulichtarm), Schichthöhe 0,2 mm, mindestens 3 Wände, Füllung ≥ 30 %.

## Hinweise zum Aufbau

- **Streuscheibe vor dem Spalt ist Pflicht.** Ohne sie hängen Helligkeit und Lage des Spektrums stark von der Lampenposition ab.
- **Kamera mittig und dicht vor das Okular** setzen und auf das Spektrum scharfstellen.
- **Kamerakabel zugentlasten.** Ein gelöstes Flachbandkabel zeigt sich als „Camera frontend has timed out“.
- **Streulicht vermeiden:** Fällt Licht am Spektroskop vorbei auf die Kamera, erscheint im Bild ein heller Fleck neben dem Spektrum und verfälscht die Messung. Übergang Spektroskop → Kamera abdunkeln.
