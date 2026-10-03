#!/usr/bin/env python3
"""Touch-Kalibrierung fuer das 3,5"-Display (labwc/libinput).

Zeigt fuenf Zielkreuze, nimmt die angetippten Koordinaten auf und berechnet
per Ausgleichsrechnung eine affine Korrektur im libinput-Format
(calibrationMatrix a b c d e f, normierte Koordinaten 0..1).
Voraussetzung: Beim Messen ist noch KEINE calibrationMatrix aktiv.
"""
import json
import tkinter as tk
from pathlib import Path

ERGEBNIS = Path.home() / "touch_kalibrierung.json"
RAND = 0.12      # Abstand der Kreuze vom Rand (Anteil der Bildgroesse)
WIEDERHOLUNGEN = 2  # jedes Kreuz zweimal antippen, Mittelwert


def loese3(m, v):
    """Loest m*x = v fuer 3x3 per Gauss-Elimination."""
    a = [row[:] + [v[i]] for i, row in enumerate(m)]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(a[r][i]))
        a[i], a[p] = a[p], a[i]
        for r in range(3):
            if r != i:
                f = a[r][i] / a[i][i]
                a[r] = [x - f * y for x, y in zip(a[r], a[i])]
    return [a[i][3] / a[i][i] for i in range(3)]


def fit(ist, soll):
    """Kleinste Quadrate: soll = k0*x + k1*y + k2."""
    ata = [[0.0] * 3 for _ in range(3)]
    atb = [0.0] * 3
    for (x, y), s in zip(ist, soll):
        z = (x, y, 1.0)
        for i in range(3):
            atb[i] += z[i] * s
            for j in range(3):
                ata[i][j] += z[i] * z[j]
    return loese3(ata, atb)


class Kalibrierung:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="black", cursor="none")
        self.root.update()
        self.w = self.root.winfo_screenwidth()
        self.h = self.root.winfo_screenheight()
        self.c = tk.Canvas(self.root, width=self.w, height=self.h,
                           bg="black", highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        r = RAND
        self.ziele = [(r, r), (1 - r, r), (1 - r, 1 - r), (r, 1 - r), (0.5, 0.5)]
        self.folge = [z for z in self.ziele for _ in range(WIEDERHOLUNGEN)]
        self.messung = []
        self.c.bind("<ButtonPress-1>", self.tipp)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.zeige()

    def zeige(self):
        self.c.delete("all")
        n = len(self.messung)
        zx, zy = self.folge[n]
        x, y = zx * self.w, zy * self.h
        self.c.create_line(x - 18, y, x + 18, y, fill="white", width=2)
        self.c.create_line(x, y - 18, x, y + 18, fill="white", width=2)
        self.c.create_oval(x - 6, y - 6, x + 6, y + 6, outline="#e04040", width=2)
        self.c.create_text(self.w / 2, self.h / 2 + (60 if zy == 0.5 else 0),
                           fill="#aaaaaa", font=("DejaVu Sans", 13),
                           text=f"Kreuzmitte genau antippen ({n + 1}/{len(self.folge)})")

    def tipp(self, e):
        self.messung.append((e.x_root / self.w, e.y_root / self.h))
        if len(self.messung) < len(self.folge):
            self.zeige()
        else:
            self.auswerten()

    def auswerten(self):
        k = WIEDERHOLUNGEN
        ist = []
        for i in range(len(self.ziele)):
            pts = self.messung[i * k:(i + 1) * k]
            ist.append((sum(p[0] for p in pts) / k, sum(p[1] for p in pts) / k))
        a, b, c = fit(ist, [z[0] for z in self.ziele])
        d, e, f = fit(ist, [z[1] for z in self.ziele])
        rest = []
        for (x, y), (sx, sy) in zip(ist, self.ziele):
            rest.append(max(abs(a * x + b * y + c - sx) * self.w,
                            abs(d * x + e * y + f - sy) * self.h))
        ergebnis = {
            "matrix": [a, b, c, d, e, f],
            "bildschirm": [self.w, self.h],
            "ziele": self.ziele,
            "gemessen_mittel": ist,
            "gemessen_roh": self.messung,
            "restfehler_px": rest,
        }
        ERGEBNIS.write_text(json.dumps(ergebnis, indent=2))
        self.c.delete("all")
        self.c.create_text(self.w / 2, self.h / 2, fill="white",
                           font=("DejaVu Sans", 14),
                           text="Kalibrierung aufgenommen.\nClaude uebernimmt die Werte.")
        self.root.after(3000, self.root.destroy)


if __name__ == "__main__":
    Kalibrierung().root.mainloop()
