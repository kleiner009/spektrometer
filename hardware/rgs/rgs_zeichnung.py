"""Technische Zeichnungen RGS v1.0 (Raster-Grundplatten-System) als SVG, A3 quer, Maße in mm.

Blatt 1: Grundplatte 125 x 125 (Draufsicht 1:1, Schnitt A-A, Einzelheiten 5:1)
Blatt 2: Verbinder (Doppel-Schwalbenschwanz) und Abschlussblende
Alle Geometrien werden aus den Parametern unten berechnet (= Spezifikation RGS v1.0).
Aufruf: python rgs_zeichnung.py  -> RGS_Blatt1_Grundplatte.svg, RGS_Blatt2_Verbinder_Blende.svg
"""
import math
import os

# ---------------------------------------------------------------- Parameter (RGS v1.0)
P = 12.5          # Rasterabstand
N = 10            # Rasterpunkte je Richtung (125 x 125)
B = 125.0         # Plattenbreite
T = 6.0           # Plattendicke
SB = 3.4          # Schlitzbreite
LA = 8.4          # Kreuzloch ueber alles
DS = 6.8          # Senkung unten (90 Grad)
TS = (DS - SB) / 2  # Senkungstiefe = 1,7
TT = 4.2          # Taschentiefe von unten
HALS, ENDE, LS = 6.0, 10.0, 10.0  # Tasche: Hals an der Kante, Ende, Laenge
SP = 0.15         # Spiel je Seite Verbinder
VH, VE, VL, VT = HALS - 2 * SP, ENDE - 2 * SP, LS - SP, 4.0  # Verbinder: 5,7 / 9,7 / 9,85 / 4,0
BL_D, BL_H = 3.0, 6.0  # Abschlussblende Dicke, Hoehe
TASCHEN = (31.25, 93.75)  # Lage der Taschen je 125er-Kante (Spalten/Zeilen C und H)

DUENN, DICK = 0.18, 0.5
FONT = "Arial, Helvetica, sans-serif"


class Blatt:
    def __init__(self):
        self.e = []

    def add(self, s):
        self.e.append(s)

    def line(self, x1, y1, x2, y2, w=DUENN, art=None, farbe="#000"):
        d = {"strich": ' stroke-dasharray="1.5,0.8"', "mitte": ' stroke-dasharray="6,1,0.8,1"', None: ""}[art]
        self.add(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="{farbe}" stroke-width="{w}"{d}/>')

    def poly(self, pts, w=DICK, fill="none", art=None, schliessen=True):
        d = ' stroke-dasharray="1.5,0.8"' if art == "strich" else ""
        tag = "polygon" if schliessen else "polyline"
        p = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
        self.add(f'<{tag} points="{p}" fill="{fill}" stroke="#000" stroke-width="{w}"{d} stroke-linejoin="round"/>')

    def path(self, d, w=DICK, fill="none", art=None):
        a = ' stroke-dasharray="1.5,0.8"' if art == "strich" else ""
        self.add(f'<path d="{d}" fill="{fill}" stroke="#000" stroke-width="{w}"{a} stroke-linejoin="round"/>')

    def text(self, x, y, s, h=2.5, anker="middle", dreh=0, fett=False):
        r = f' transform="rotate({dreh} {x:.3f} {y:.3f})"' if dreh else ""
        f = ' font-weight="bold"' if fett else ""
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.add(f'<text x="{x:.3f}" y="{y:.3f}" font-family="{FONT}" font-size="{h}" text-anchor="{anker}"{f}{r}>{s}</text>')

    def pfeil(self, x, y, wx, wy):
        """Pfeilspitze bei (x,y), zeigt in Richtung (wx,wy)."""
        l = math.hypot(wx, wy); wx, wy = wx / l, wy / l
        a, b = 2.2, 0.45
        p1 = (x - wx * a - wy * b, y - wy * a + wx * b)
        p2 = (x - wx * a + wy * b, y - wy * a - wx * b)
        self.add(f'<polygon points="{x:.3f},{y:.3f} {p1[0]:.3f},{p1[1]:.3f} {p2[0]:.3f},{p2[1]:.3f}" fill="#000"/>')

    def mass_h(self, x1, x2, y_obj, y_mass, txt, aussen=False):
        """Waagerechtes Maß zwischen x1 und x2; Hilfslinien von y_obj bis y_mass."""
        s = 1 if y_mass > y_obj else -1
        for x in (x1, x2):
            self.line(x, y_obj + s * 0.8, x, y_mass + s * 1.5)
        if aussen or abs(x2 - x1) < 6:
            self.line(x1 - 5, y_mass, x2 + 5, y_mass)
            self.pfeil(x1, y_mass, 1, 0); self.pfeil(x2, y_mass, -1, 0)
        else:
            self.line(x1, y_mass, x2, y_mass)
            self.pfeil(x1, y_mass, -1, 0); self.pfeil(x2, y_mass, 1, 0)
        self.text((x1 + x2) / 2, y_mass - 0.9, txt)

    def mass_v(self, y1, y2, x_obj, x_mass, txt, aussen=False):
        s = 1 if x_mass > x_obj else -1
        for y in (y1, y2):
            self.line(x_obj + s * 0.8, y, x_mass + s * 1.5, y)
        if aussen or abs(y2 - y1) < 6:
            self.line(x_mass, min(y1, y2) - 5, x_mass, max(y1, y2) + 5)
            self.pfeil(x_mass, min(y1, y2), 0, 1); self.pfeil(x_mass, max(y1, y2), 0, -1)
        else:
            self.line(x_mass, y1, x_mass, y2)
            self.pfeil(x_mass, min(y1, y2), 0, -1); self.pfeil(x_mass, max(y1, y2), 0, 1)
        self.text(x_mass - 0.9, (y1 + y2) / 2, txt, dreh=-90)

    def hinweis(self, x, y, xt, yt, txt, anker="start"):
        """Hinweislinie mit Text."""
        self.line(x, y, xt, yt)
        self.add(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="0.4" fill="#000"/>')
        self.line(xt, yt, xt + (18 if anker == "start" else -18), yt)
        self.text(xt + (1 if anker == "start" else -1), yt - 0.8, txt, anker=anker)

    def rahmen(self, titel, blatt, massstab):
        self.add('<rect x="10" y="10" width="400" height="277" fill="none" stroke="#000" stroke-width="0.7"/>')
        x0, y0 = 250, 252
        self.add(f'<rect x="{x0}" y="{y0}" width="160" height="35" fill="none" stroke="#000" stroke-width="0.5"/>')
        for yy in (y0 + 12, y0 + 19, y0 + 26):
            self.line(x0, yy, 410, yy)
        self.line(x0 + 80, y0 + 12, x0 + 80, 287)
        self.text(x0 + 3, y0 + 5.5, "RGS – Raster-Grundplatten-System v1.0", h=3.5, anker="start", fett=True)
        self.text(x0 + 3, y0 + 10.5, titel, h=3.0, anker="start")
        self.text(x0 + 3, y0 + 17, "Werkstoff: PETG schwarz matt (FDM)", anker="start")
        self.text(x0 + 83, y0 + 17, f"Maßstab: {massstab}", anker="start")
        self.text(x0 + 3, y0 + 24, "Allgemeintoleranz: ±0,2 mm", anker="start")
        self.text(x0 + 83, y0 + 24, "Maße in mm", anker="start")
        self.text(x0 + 3, y0 + 31.5, "Erstellt: 2026-10-03 · Stand: Entwurf", anker="start")
        self.text(x0 + 83, y0 + 31.5, f"Blatt {blatt} von 2", anker="start")

    def speichern(self, pfad):
        kopf = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297">\n'
                '<defs><pattern id="schraffur" width="1.6" height="1.6" patternUnits="userSpaceOnUse" '
                'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="1.6" stroke="#000" stroke-width="0.15"/>'
                '</pattern></defs>\n<rect width="420" height="297" fill="#fff"/>\n')
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(kopf + "\n".join(self.e) + "\n</svg>\n")


def kreuz_pfad(cx, cy, l, b, k=1.0):
    """Kreuzloch mit runden Enden, Mittelpunkt (cx,cy), im Uhrzeigersinn (SVG-Koordinaten), Massstab k."""
    l, b = l * k, b * k
    a, h, r = l / 2 - b / 2, b / 2, b / 2
    pts = [("M", -h, -h), ("L", -h, -a), ("A", h, -a), ("L", h, -h), ("L", a, -h), ("A", a, h),
           ("L", h, h), ("L", h, a), ("A", -h, a), ("L", -h, h), ("L", -a, h), ("A", -a, -h)]
    d = ""
    for c, x, y in pts:
        if c == "A":
            d += f" A {r:.3f} {r:.3f} 0 0 1 {cx + x:.3f} {cy + y:.3f}"
        else:
            d += f" {c} {cx + x:.3f} {cy + y:.3f}"
    return d + " Z"


def kreuz_kontur(cx, cy, r, k=1.0, n=240):
    """Kontur im Abstand r um das Kreuz-Skelett (zwei Strecken +-a, a = LA/2 - SB/2).
    r = SB/2 -> Schlitz, r = SB/2 + TS -> Senkung an der Unterseite (exakter Versatz)."""
    a = LA / 2 - SB / 2

    def abstand(x, y):
        d1 = math.hypot(max(abs(x) - a, 0), y)
        d2 = math.hypot(x, max(abs(y) - a, 0))
        return min(d1, d2)
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        ux, uy = math.cos(t), math.sin(t)
        lo, hi = 0.0, a + r + 1
        for _ in range(40):
            m = (lo + hi) / 2
            if abstand(m * ux, m * uy) < r:
                lo = m
            else:
                hi = m
        pts.append((cx + lo * ux * k, cy + lo * uy * k))
    return pts


def tasche_pts(kante_x, kante_y, richtung, hals, ende, laenge, k=1.0):
    """Trapez der Tasche/Zunge: Hals an der Kante (Mitte kante_x/y), Ende nach 'richtung' (dx,dy)."""
    dx, dy = richtung
    qx, qy = -dy, dx
    h, e, l = hals * k / 2, ende * k / 2, laenge * k
    return [(kante_x + qx * h, kante_y + qy * h), (kante_x + dx * l + qx * e, kante_y + dy * l + qy * e),
            (kante_x + dx * l - qx * e, kante_y + dy * l - qy * e), (kante_x - qx * h, kante_y - qy * h)]


# ======================================================================== Blatt 1
def blatt1():
    s = Blatt()
    s.rahmen("Grundplatte 125 × 125 × 6 (Variante 125 × 250 siehe Hinweis 5)", 1, "1:1, Einzelheiten 5:1")

    # ---------------- Draufsicht 1:1
    ox, oy = 42.0, 34.0              # linke obere Ecke der Platte
    X = lambda x: ox + x             # Plattenkoordinate x -> Blatt
    Y = lambda y: oy + B - y         # y nach oben (Zeile 1 vorn = unten)
    s.text(X(B / 2), 22, "Draufsicht", h=3.5, fett=True)
    s.add(f'<rect x="{ox}" y="{oy}" width="{B}" height="{B}" rx="2" fill="none" stroke="#000" stroke-width="{DICK}"/>')
    weg = set()
    for t in TASCHEN:
        i = int(round((t - P / 2) / P))
        weg |= {(i, 0), (i, N - 1), (0, i), (N - 1, i)}
    for i in range(N):
        for j in range(N):
            cx, cy = X(P / 2 + i * P), Y(P / 2 + j * P)
            if (i, j) in weg:
                continue
            s.poly(kreuz_kontur(cx, cy, SB / 2, n=96), w=0.3)
    # Taschen (unten -> verdeckt)
    for t in TASCHEN:
        s.poly(tasche_pts(X(t), Y(0), (0, -1), HALS, ENDE, LS), w=0.3, art="strich")
        s.poly(tasche_pts(X(t), Y(B), (0, 1), HALS, ENDE, LS), w=0.3, art="strich")
        s.poly(tasche_pts(X(0), Y(t), (1, 0), HALS, ENDE, LS), w=0.3, art="strich")
        s.poly(tasche_pts(X(B), Y(t), (-1, 0), HALS, ENDE, LS), w=0.3, art="strich")
    # Spalten/Zeilen-Beschriftung
    for i in range(N):
        s.text(X(P / 2 + i * P), oy - 2.5, "ABCDEFGHIJ"[i], h=2.8)
        s.text(ox - 3.5, Y(P / 2 + i * P) + 1, str(i + 1), h=2.8)
    # Mittellinien Spalte C / Zeile 3 + Schnittlinie A-A durch Zeile 3
    ya = Y(TASCHEN[0])
    s.line(ox - 8, ya, ox + B + 8, ya, w=0.35, art="mitte")
    for xx, d in ((ox - 8, 1), (ox + B + 8, -1)):
        s.line(xx, ya, xx, ya + 5, w=DICK); s.pfeil(xx, ya + 5.5, 0, 1)
        s.text(xx, ya + 10, "A", h=3.5, fett=True)
    # Maße Draufsicht (unten)
    yb = oy + B
    s.mass_h(X(0), X(P / 2), yb, yb + 6, "6,25", aussen=True)
    s.mass_h(X(P / 2 + P), X(P / 2 + 2 * P), yb, yb + 6, "12,5 (Raster)")
    s.mass_h(X(0), X(TASCHEN[0]), yb, yb + 13, "31,25 ±0,1")
    s.mass_h(X(0), X(TASCHEN[1]), yb, yb + 20, "93,75 ±0,1")
    s.mass_h(X(0), X(B), yb, yb + 27, "125 −0,2/0")
    # Maße Draufsicht (links)
    s.mass_v(Y(0), Y(B), ox, ox - 20, "125 −0,2/0")
    s.mass_v(Y(0), Y(P / 2), ox, ox - 12, "6,25", aussen=True)
    # Hinweise in der Draufsicht
    s.hinweis(X(B) - 0.6, oy + 0.6, X(B) + 8, oy - 4, "R2 (4×)")
    s.hinweis(X(B - P / 2) + 2.2, Y(B - P / 2 - P) - 0.5, X(B) + 8, oy + 14, "Kreuzloch, s. Einzelheit X")
    s.hinweis(X(B) - LS + 1, Y(TASCHEN[1]), X(B) + 8, oy + 31, "Tasche (unten), s. Einzelheit Z")
    for n, z in enumerate(["Verbinderplätze C1, H1, C10,", "H10, A3, A8, J3, J8:", "kein Kreuzloch", "",
                           "Gravur A–J / 1–10 oben,", "0,4 tief, Schrifthöhe 4"]):
        s.text(X(B) + 9, oy + 48 + n * 3.6, z, anker="start")

    # ---------------- Schnitt A-A (1:1) durch Zeile 3, unterhalb
    sy = 205.0          # Blatt-y der Plattenoberseite
    Z = lambda z: sy + T - z
    s.text(X(B / 2), sy - 6, "Schnitt A–A (1:1)", h=3.5, fett=True)
    s.add(f'<rect x="{ox}" y="{sy}" width="{B}" height="{T}" fill="url(#schraffur)" stroke="none"/>')
    leer = []
    for i in range(1, N - 1):     # A3 und J3 sind Taschenplaetze
        c = P / 2 + i * P
        leer.append([(X(c - LA / 2 - TS), Z(0)), (X(c + LA / 2 + TS), Z(0)), (X(c + LA / 2), Z(TS)),
                     (X(c + LA / 2), Z(T)), (X(c - LA / 2), Z(T)), (X(c - LA / 2), Z(TS))])
    leer.append([(X(0), Z(0)), (X(LS), Z(0)), (X(LS), Z(TT)), (X(0), Z(TT))])
    leer.append([(X(B - LS), Z(0)), (X(B), Z(0)), (X(B), Z(TT)), (X(B - LS), Z(TT))])
    for p in leer:
        s.poly(p, w=0.01, fill="#fff")
    # Kontur: Oberseite, Unterseite stueckweise
    s.line(X(0), Z(T), X(B), Z(T), w=DICK)
    s.line(X(0), Z(TT), X(0), Z(T), w=DICK); s.line(X(B), Z(TT), X(B), Z(T), w=DICK)
    for p in leer:
        s.poly(p, w=DICK, schliessen=False)
    for i in range(N - 1):
        pass
    kanten = [X(LS)] + [v for i in range(1, N - 1) for v in (X(P / 2 + i * P - LA / 2 - TS), X(P / 2 + i * P + LA / 2 + TS))] + [X(B - LS)]
    for a, b in zip(kanten[0::2], kanten[1::2]):
        s.line(a, Z(0), b, Z(0), w=DICK)
    s.mass_v(Z(0), Z(T), X(B), X(B) + 8, "6 ±0,2", aussen=True)
    s.mass_h(X(0), X(LS), Z(0), Z(0) + 7, "10", aussen=True)
    s.text(X(B / 2), Z(0) + 14, "Oberseite oben · Unterseite (Senkungen, Taschen) liegt beim Druck auf dem Bett", h=2.5)

    # ---------------- Einzelheit X: Kreuzloch Draufsicht 5:1
    k = 5
    cx, cy = 262.0, 78.0
    s.text(cx, 30, "Einzelheit X (5:1)", h=3.5, fett=True)
    s.text(cx, 34.5, "Kreuzloch, Draufsicht", h=2.5)
    s.poly(kreuz_kontur(cx, cy, SB / 2 + TS, k), w=0.3, art="strich")
    s.poly(kreuz_kontur(cx, cy, SB / 2, k), w=DICK)
    s.line(cx - 36, cy, cx + 36, cy, art="mitte"); s.line(cx, cy - 36, cx, cy + 36, art="mitte")
    s.mass_h(cx - SB * k / 2, cx + SB * k / 2, cy - LA * k / 2, cy - LA * k / 2 - 8, "3,4 +0,1/0")
    s.mass_v(cy - LA * k / 2, cy + LA * k / 2, cx + SB * k / 2, cx + 40, "8,4 ±0,1")
    s.mass_h(cx - (LA + 2 * TS) * k / 2, cx + (LA + 2 * TS) * k / 2, cy + DS * k / 2, cy + 40, "11,8 (Senkung unten, verdeckt)")
    s.text(cx, cy + 48, "Schlitzenden halbrund (R1,7)", h=2.5)
    s.text(cx, cy + 51.5, "Senkung = Schlitzkontur um 1,7 versetzt", h=2.5)

    # ---------------- Einzelheit Y: Schnitt quer durch Kreuzarm 5:1
    cx, by = 362.0, 92.0       # by = Blatt-y der Unterseite
    Zk = lambda z: by - z * k
    Xk = lambda x: cx + x * k
    s.text(cx, 30, "Einzelheit Y (5:1)", h=3.5, fett=True)
    s.text(cx, 34.5, "Schnitt quer durch einen Kreuzarm", h=2.5)
    breite = 7.0
    s.add(f'<rect x="{Xk(-breite):.3f}" y="{Zk(T):.3f}" width="{2 * breite * k}" height="{T * k}" fill="url(#schraffur)"/>')
    loch = [(Xk(-DS / 2), Zk(0)), (Xk(DS / 2), Zk(0)), (Xk(SB / 2), Zk(TS)), (Xk(SB / 2), Zk(T)), (Xk(-SB / 2), Zk(T)), (Xk(-SB / 2), Zk(TS))]
    s.poly(loch, w=0.01, fill="#fff")
    s.poly([(Xk(-breite), Zk(T)), (Xk(-SB / 2), Zk(T)), (Xk(-SB / 2), Zk(TS)), (Xk(-DS / 2), Zk(0)), (Xk(-breite), Zk(0))], schliessen=False)
    s.poly([(Xk(breite), Zk(T)), (Xk(SB / 2), Zk(T)), (Xk(SB / 2), Zk(TS)), (Xk(DS / 2), Zk(0)), (Xk(breite), Zk(0))], schliessen=False)
    s.line(Xk(-breite), Zk(T), Xk(-breite), Zk(0), art="strich"); s.line(Xk(breite), Zk(T), Xk(breite), Zk(0), art="strich")
    s.line(cx, Zk(T) - 5, cx, Zk(0) + 5, art="mitte")
    s.mass_h(Xk(-SB / 2), Xk(SB / 2), Zk(T), Zk(T) - 7, "3,4 +0,1/0")
    s.mass_h(Xk(-DS / 2), Xk(DS / 2), Zk(0), Zk(0) + 8, "6,8 +0,2/0 (Senkung 90°)")
    s.mass_v(Zk(0), Zk(T), Xk(breite), Xk(breite) + 8, "6 ±0,2")
    s.mass_v(Zk(0), Zk(TS), Xk(-breite), Xk(-breite) - 8, "1,7", aussen=True)
    s.text(cx, Zk(0) + 17, "M3 × 10 ISO 10642: Kopf bündig bis 1,4 versenkt (Kreuzmitte: Anlage an 4 Ecken)", h=2.5)

    # ---------------- Einzelheit Z: Tasche, Ansicht von unten 5:1
    cx, ky = 262.0, 158.0      # ky = Blatt-y der Plattenkante
    s.text(cx, 141, "Einzelheit Z (5:1)", h=3.5, fett=True)
    s.text(cx, 145.5, "Tasche, Ansicht von UNTEN", h=2.5)
    s.line(cx - 35, ky, cx + 35, ky, w=DICK)
    s.text(cx - 36, ky - 1.5, "Plattenkante", anker="start")
    tp = tasche_pts(cx, ky, (0, 1), HALS, ENDE, LS, k)
    s.poly(tp, w=DICK)
    s.line(cx, ky - 4, cx, ky + LS * k + 4, art="mitte")
    s.mass_h(cx - HALS * k / 2, cx + HALS * k / 2, ky, ky - 7, "6,0 +0,1/0")
    s.mass_h(cx - ENDE * k / 2, cx + ENDE * k / 2, ky + LS * k, ky + LS * k + 8, "10,0 +0,1/0")
    s.mass_v(ky, ky + LS * k, cx + ENDE * k / 2, cx + ENDE * k / 2 + 9, "10,0 +0,1/0")
    s.text(cx, ky + LS * k + 15, "Innenecken R0,5 · Lage: Spalte/Zeile C und H", h=2.5)

    # ---------------- Einzelheit W: Tasche im Schnitt 5:1
    cx0, by = 330.0, 212.0     # cx0 = Plattenkante, by = Unterseite
    s.text(365, 168, "Einzelheit W (5:1)", h=3.5, fett=True)
    s.text(365, 172.5, "Tasche im Schnitt (Mitte Tasche)", h=2.5)
    lx = 14.0
    s.add(f'<rect x="{cx0:.3f}" y="{by - T * k:.3f}" width="{lx * k}" height="{T * k}" fill="url(#schraffur)"/>')
    s.poly([(cx0, by), (cx0 + LS * k, by), (cx0 + LS * k, by - TT * k), (cx0, by - TT * k)], w=0.01, fill="#fff")
    s.poly([(cx0, by - TT * k), (cx0, by - T * k), (cx0 + lx * k, by - T * k)], schliessen=False)
    s.poly([(cx0, by - TT * k), (cx0 + LS * k, by - TT * k), (cx0 + LS * k, by), (cx0 + lx * k, by)], schliessen=False)
    s.line(cx0 + lx * k, by, cx0 + lx * k, by - T * k, art="strich")
    s.mass_v(by, by - TT * k, cx0, cx0 - 8, "4,2 +0,2/0")
    s.mass_v(by - TT * k, by - T * k, cx0, cx0 - 8, "1,8", aussen=True)
    s.mass_h(cx0, cx0 + LS * k, by, by + 7, "10,0 +0,1/0")
    s.mass_v(by, by - T * k, cx0 + lx * k, cx0 + lx * k + 7, "6 ±0,2")

    # ---------------- Hinweise
    hx, hy = 14.0, 252.0
    zeilen = ["Hinweise:",
              "1  Nicht tolerierte Maße: ±0,2 (FDM). Rasterlage der Kreuzlöcher ±0,1 zueinander.",
              "2  Druck mit der Unterseite aufs Bett, Schichthöhe 0,2, ≥ 3 Wände; Elefantenfuß kompensieren (Senkungen/Taschen).",
              "3  Kreuzloch an jedem Rasterpunkt (Raster 12,5, erster Punkt 6,25 vom Rand) außer an den Verbinderplätzen.",
              "4  Plattenmaß 125 −0,2/0: zwei Platten dürfen sich nicht überdecken, Rasterversatz an der Stoßstelle max. 0,2.",
              "5  Variante 125 × 250: 10 × 20 Raster, Taschen an den langen Kanten bei 31,25 / 93,75 / 156,25 / 218,75.",
              "6  Vor dem ersten Druck Testkörper 37,5 × 37,5 (3 × 3 Raster, 1 Tasche) drucken und Passungen prüfen."]
    for n, z in enumerate(zeilen):
        s.text(hx, hy + n * 4.8, z, h=2.6 if n else 3.0, anker="start", fett=(n == 0))
    return s


# ======================================================================== Blatt 2
def blatt2():
    s = Blatt()
    s.rahmen("Verbinder (Doppel-Schwalbenschwanz) und Abschlussblende", 2, "5:1, Blende 1:1")
    k = 5

    # ---------------- Verbinder Draufsicht 5:1
    cx, cy = 95.0, 70.0
    s.text(cx, 28, "Verbinder – Draufsicht (5:1)", h=3.5, fett=True)
    pts = [(-VL, -VE / 2), (0, -VH / 2), (VL, -VE / 2), (VL, VE / 2), (0, VH / 2), (-VL, VE / 2)]
    s.poly([(cx + x * k, cy + y * k) for x, y in pts])
    s.line(cx - VL * k - 5, cy, cx + VL * k + 5, cy, art="mitte"); s.line(cx, cy - VE * k / 2 - 5, cx, cy + VE * k / 2 + 5, art="mitte")
    s.mass_h(cx - VL * k, cx + VL * k, cy - VE * k / 2, cy - VE * k / 2 - 9, "19,7 0/−0,2")
    s.mass_h(cx - VL * k, cx, cy + VE * k / 2, cy + VE * k / 2 + 8, "9,85 0/−0,1")
    s.mass_v(cy - VE * k / 2, cy + VE * k / 2, cx + VL * k, cx + VL * k + 9, "9,7 0/−0,1")
    s.mass_v(cy - VH * k / 2, cy + VH * k / 2, cx, cx - 12, "5,7 0/−0,1")
    s.text(cx, cy + VE * k / 2 + 17, "Ecken R0,5 (außen gebrochen)", h=2.5)

    # ---------------- Verbinder Seitenansicht 5:1
    cy2 = 132.0
    s.text(cx, cy2 - 7, "Verbinder – Seitenansicht (5:1)", h=3.5, fett=True)
    s.add(f'<rect x="{cx - VL * k:.3f}" y="{cy2:.3f}" width="{2 * VL * k}" height="{VT * k}" fill="none" stroke="#000" stroke-width="{DICK}"/>')
    s.mass_v(cy2, cy2 + VT * k, cx + VL * k, cx + VL * k + 9, "4,0 0/−0,1")

    # ---------------- Einbausituation 2:1
    k2 = 2.5
    ex, ez = 95.0, 200.0      # ex = Stoßstelle, ez = Unterseite
    s.text(ex, 160, "Einbausituation – Schnitt (2,5:1)", h=3.5, fett=True)
    breite = 16.0
    for sgn in (-1, 1):
        x_aussen = ex + sgn * breite * k2
        s.add(f'<rect x="{min(ex, x_aussen):.3f}" y="{ez - T * k2:.3f}" width="{breite * k2}" height="{T * k2}" fill="url(#schraffur)"/>')
        s.poly([(ex, ez), (ex + sgn * LS * k2, ez), (ex + sgn * LS * k2, ez - TT * k2), (ex, ez - TT * k2)], w=0.01, fill="#fff")
        s.poly([(ex, ez - TT * k2), (ex, ez - T * k2), (x_aussen, ez - T * k2)], schliessen=False)
        s.poly([(ex, ez - TT * k2), (ex + sgn * LS * k2, ez - TT * k2), (ex + sgn * LS * k2, ez), (x_aussen, ez)], schliessen=False)
    s.add(f'<rect x="{ex - VL * k2:.3f}" y="{ez - VT * k2:.3f}" width="{2 * VL * k2}" height="{VT * k2}" fill="#bbb" stroke="#000" stroke-width="{DICK}"/>')
    s.text(ex - breite * k2 + 2, ez - T * k2 - 2, "Platte 1", anker="start")
    s.text(ex + breite * k2 - 2, ez - T * k2 - 2, "Platte 2", anker="end")
    s.hinweis(ex + 4, ez - VT * k2 / 2, ex + 30, ez + 12, "Verbinder (von unten eingesteckt)")
    s.text(ex, ez + 22, "Spiel: seitlich 0,15 je Seite (min.), Höhe 0,2 (min.) · oben bleiben 1,8 Deckschicht", h=2.5)

    # ---------------- Abschlussblende Draufsicht 1:1
    bx, by = 200.0, 42.0       # linke Ecke, Außenkante
    s.text(bx + B / 2, 28, "Abschlussblende – Draufsicht (1:1)", h=3.5, fett=True)
    kontur = [(bx, by), (bx + B, by), (bx + B, by + BL_D)]
    for t in reversed(TASCHEN):
        z = tasche_pts(bx + t, by + BL_D, (0, 1), VH, VE, VL)
        kontur += [z[3], z[2], z[1], z[0]]
    kontur += [(bx, by + BL_D)]
    s.poly(kontur)
    s.mass_h(bx, bx + B, by, by - 6, "125 −0,2/0")
    s.mass_h(bx, bx + TASCHEN[0], by + BL_D + VL, by + BL_D + VL + 7, "31,25 ±0,1")
    s.mass_h(bx, bx + TASCHEN[1], by + BL_D + VL, by + BL_D + VL + 14, "93,75 ±0,1")
    s.mass_v(by, by + BL_D, bx, bx - 8, "3 ±0,2", aussen=True)
    s.text(bx + B / 2, by + BL_D + VL + 22, "Zungen = halber Verbinder (5,7 / 9,7 / 9,85, Höhe 4,0 – siehe links)", h=2.5)

    # ---------------- Abschlussblende Vorderansicht 1:1
    vy = 100.0
    s.text(bx + B / 2, vy - 7, "Abschlussblende – Ansicht von außen (1:1)", h=3.5, fett=True)
    s.add(f'<rect x="{bx}" y="{vy}" width="{B}" height="{BL_H}" fill="none" stroke="#000" stroke-width="{DICK}"/>')
    for t in TASCHEN:
        s.add(f'<rect x="{bx + t - VE / 2:.3f}" y="{vy + BL_H - VT:.3f}" width="{VE}" height="{VT}" fill="none" stroke="#000" stroke-width="0.3" stroke-dasharray="1.5,0.8"/>')
    s.mass_v(vy, vy + BL_H, bx + B, bx + B + 8, "6 ±0,2", aussen=True)

    # ---------------- Abschlussblende Schnitt 5:1
    sx, sz = 300.0, 190.0       # sx = Außenkante, sz = Unterseite
    s.text(sx + 30, 143, "Abschlussblende – Schnitt durch Zunge (5:1)", h=3.5, fett=True)
    form = [(sx, sz), (sx, sz - BL_H * k), (sx + BL_D * k, sz - BL_H * k), (sx + BL_D * k, sz - VT * k),
            (sx + (BL_D + VL) * k, sz - VT * k), (sx + (BL_D + VL) * k, sz)]
    s.poly(form, fill="url(#schraffur)")
    s.mass_h(sx, sx + BL_D * k, sz - BL_H * k, sz - BL_H * k - 7, "3 ±0,2")
    s.mass_h(sx + BL_D * k, sx + (BL_D + VL) * k, sz, sz + 8, "9,85 0/−0,1")
    s.mass_v(sz, sz - BL_H * k, sx, sx - 8, "6 ±0,2")
    s.mass_v(sz, sz - VT * k, sx + (BL_D + VL) * k, sx + (BL_D + VL) * k + 8, "4,0 0/−0,1")
    s.text(sx + 30, sz + 17, "Zunge unten bündig · Oberkante Blende bündig mit Plattenoberseite", h=2.5)

    # ---------------- Passungstabelle
    tx, ty = 14.0, 236.0
    s.text(tx, ty, "Passungen (Tasche ↔ Verbinder/Zunge)", h=3.0, anker="start", fett=True)
    kopf = ["Maß", "Tasche", "Verbinder", "Spiel min. … max."]
    reihen = [["Hals", "6,0 +0,1/0", "5,7 0/−0,1", "0,30 … 0,50"],
              ["Ende", "10,0 +0,1/0", "9,7 0/−0,1", "0,30 … 0,50"],
              ["Länge je Seite", "10,0 +0,1/0", "9,85 0/−0,1", "0,15 … 0,35"],
              ["Höhe/Tiefe", "4,2 +0,2/0", "4,0 0/−0,1", "0,20 … 0,50"]]
    spalten = [0, 32, 62, 92]
    for n, r in enumerate([kopf] + reihen):
        for c, w in zip(spalten, r):
            s.text(tx + c, ty + 6 + n * 4.6, w, h=2.6, anker="start", fett=(n == 0))
    s.line(tx, ty + 7.3, tx + 130, ty + 7.3)
    s.text(tx, ty + 34, "Spiel 'seitlich' je Seite = Hälfte der Werte. Zu stramm: Verbinder 0,1 schmaler; zu locker: Spiel verkleinern.", h=2.5, anker="start")
    s.text(tx, ty + 38.5, "Werte nach Testdruck anpassen und als v1.1 festhalten.", h=2.5, anker="start")
    return s


if __name__ == "__main__":
    hier = os.path.dirname(os.path.abspath(__file__))
    blatt1().speichern(os.path.join(hier, "RGS_Blatt1_Grundplatte.svg"))
    blatt2().speichern(os.path.join(hier, "RGS_Blatt2_Verbinder_Blende.svg"))
    print("ok")
