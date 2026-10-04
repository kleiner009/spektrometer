#!/usr/bin/env python3
"""Gefuehrte Kalibrierung des Spektrometers am Touchdisplay.

Schritte:
  1. Bildausschnitt  - weisses Licht vor den Spalt, Spektrum wird erkannt
  2. Gruener Laser   - erster Fixpunkt (Standard 532 nm)
  3. Roter Laser     - zweiter Fixpunkt (Standard 650 nm), prueft auch die Spiegelung
  4. Blauer Punkt    - optional: Blauspitze einer weissen LED (Standard 450 nm);
                       mit 3 Punkten wird die Zuordnung gekruemmt (Polynom 2. Grades)
  5. Gluehlampe      - Normkurve (Planck) fuer die Empfindlichkeitskorrektur
  6. Zusammenfassung - Speichern oder Verwerfen

Gespeichert wird erst im letzten Schritt: kamera_einstellungen.json, caldata.txt,
empfindlichkeit.csv, Protokoll in kalibrierung_protokoll.json. Alte Dateien
werden vorher nach alt/<Zeitstempel>/ gesichert.
Rueckgabewert: 0 = gespeichert, 1 = abgebrochen/verworfen.
"""
import json
import os
import shutil
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import kamera

ORDNER = os.path.dirname(os.path.abspath(__file__))
W, H = 800, 480
FENSTER = "PySpectrometer Kalibrierung"  # beginnt mit PySpectrometer -> labwc legt es aufs Display
SENSOR_W, SENSOR_H = kamera.SENSOR_W, kamera.SENSOR_H
C2 = 1.4388e-2  # zweite Strahlungskonstante in m*K
SCHRIFT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SCHRIFT_FETT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_schriften = {}


def schrift(groesse, fett=False):
	if (groesse, fett) not in _schriften:
		_schriften[(groesse, fett)] = ImageFont.truetype(SCHRIFT_FETT if fett else SCHRIFT, groesse)
	return _schriften[(groesse, fett)]


# --------------------------------------------------------------------------- Oberflaeche
class Oberflaeche:
	"""Vollbildfenster 800x480 mit Titel, Anleitung, Inhaltsbereich und Touch-Buttons."""
	INHALT = (0, 128, W, 396)  # x0, y0, x1, y1

	def __init__(self):
		cv2.namedWindow(FENSTER, cv2.WND_PROP_FULLSCREEN)
		cv2.setWindowProperty(FENSTER, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
		cv2.setMouseCallback(FENSTER, self._maus)
		self.buttons = []
		self.gedrueckt = None

	def _maus(self, ereignis, x, y, flags, param):
		if ereignis == cv2.EVENT_LBUTTONDOWN:
			for schluessel, x0, y0, x1, y1, _, _ in self.buttons:
				if x0 <= x <= x1 and y0 <= y <= y1:
					self.gedrueckt = schluessel

	def taste(self):
		"""Zuletzt gedrueckten Button einmalig zurueckgeben."""
		t, self.gedrueckt = self.gedrueckt, None
		return t

	def zeigen(self, titel, zeilen, inhalt=None, buttons=()):
		"""buttons: Liste (schluessel, beschriftung, farbe); farbe "gruen"/"rot"/"grau"/"blau"."""
		farben = {"gruen": (60, 140, 60), "rot": (60, 60, 160), "grau": (90, 90, 90), "blau": (150, 100, 40)}
		bild = np.full((H, W, 3), 245, np.uint8)
		bild[:44] = (45, 45, 45)
		if inhalt is not None:
			x0, y0, x1, y1 = self.INHALT
			bild[y0:y1, x0:x1] = cv2.resize(inhalt, (x1 - x0, y1 - y0)) if inhalt.shape[:2] != (y1 - y0, x1 - x0) else inhalt
		self.buttons = []
		if buttons:
			n = len(buttons)
			breite = (W - 8 * (n + 1)) // n
			for k, (schluessel, text, farbe) in enumerate(buttons):
				x0 = 8 + k * (breite + 8)
				self.buttons.append((schluessel, x0, 404, x0 + breite, 474, text, farben.get(farbe, farben["grau"])))
				cv2.rectangle(bild, (x0, 404), (x0 + breite, 474), farben.get(farbe, farben["grau"]), -1)
				cv2.rectangle(bild, (x0, 404), (x0 + breite, 474), (220, 220, 220), 2)
		pil = Image.fromarray(cv2.cvtColor(bild, cv2.COLOR_BGR2RGB))
		d = ImageDraw.Draw(pil)
		d.text((12, 8), titel, font=schrift(24, True), fill=(255, 255, 255))
		for i, z in enumerate(zeilen[:4]):
			d.text((12, 50 + i * 19), z, font=schrift(16), fill=(20, 20, 20))
		for _, x0, y0, x1, y1, text, _ in self.buttons:
			f = schrift(22 if len(self.buttons) <= 4 else 17 if len(self.buttons) <= 6 else 15, True)
			d.text(((x0 + x1) / 2 - d.textlength(text, font=f) / 2, 426), text, font=f, fill=(255, 255, 255))
		cv2.imshow(FENSTER, cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR))
		cv2.waitKey(1)


# --------------------------------------------------------------------------- Messhilfen
STUFEN_US = [100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000]


class Belichtung:
	"""Belichtung von Hand in festen Stufen (Buttons Dunkler/Heller).

	Eine neue Belichtung wirkt erst nach 5-7 Bildern; bild() liefert deshalb nur
	Bilder, bei denen die gewaehlte Belichtung laut Metadaten schon greift."""

	def __init__(self, cam, stufe=6, gain=4.0):
		self.cam, self.stufe, self.gain = cam, stufe, gain
		self.us = STUFEN_US[stufe]
		self._setzen()

	def _setzen(self):
		self.cam.set_controls({"ExposureTime": int(self.us), "AnalogueGain": self.gain})

	def frei_setzen(self, us):
		"""Belichtung stufenlos (fuer die automatische Regelung); Stufe folgt naeherungsweise."""
		self.us = int(min(max(us, STUFEN_US[0]), STUFEN_US[-1]))
		self.stufe = int(np.argmin([abs(np.log(self.us / s)) for s in STUFEN_US]))
		self._setzen()

	def taste(self, t):
		"""Buttons 'heller'/'dunkler' auswerten; True, wenn verstellt wurde."""
		if t == "heller" and self.stufe < len(STUFEN_US) - 1:
			self.stufe += 1
		elif t == "dunkler" and self.stufe > 0:
			self.stufe -= 1
		else:
			return False
		self.us = STUFEN_US[self.stufe]
		self._setzen()
		return True

	def bild(self, spiegeln=None):
		for _ in range(15):  # bei 1 s Belichtung max. ca. 15 s warten
			f, daten = kamera.bild_mit_daten(self.cam, spiegeln)
			if kamera.belichtung_wirksam(daten, self.us):
				return f
		return f

	def text(self, spitze):
		ms = self.us / 1000
		if spitze >= 245:
			zustand = "ÜBERSTEUERT – dunkler"
		elif spitze < 80:
			zustand = "zu schwach – heller"
		else:
			zustand = "gut"
		return "Belichtung %s ms · Spitze %d · %s" % (("%.1f" % ms) if ms < 10 else "%d" % ms, spitze, zustand)


def messen(bel, spiegeln):
	"""Ein Bild: (Messprofil = Mittel der Farbkanaele, Aussteuerung = hellster Kanal)."""
	f = bel.bild(spiegeln)
	return kamera.zeilenprofil(f), float(kamera.kanalmaximum(f).max())


def linie_finden(profil):
	"""Schmale Linie (Laser): (Schwerpunkt_px, Hoehe ueber Grund) oder (None, 0)."""
	grund = float(np.median(profil))
	i = int(np.argmax(profil))
	hoehe = profil[i] - grund
	if hoehe < 15:  # Mittel der Kanaele: ca. 1/3 des Einzelkanals
		return None, hoehe
	lo, hi = max(0, i - 40), min(len(profil), i + 41)
	gewicht = np.clip(profil[lo:hi] - grund, 0, None)
	return float((np.arange(lo, hi) * gewicht).sum() / gewicht.sum()), hoehe


def profil_bild(profil, marke=None, farbe=(0, 0, 0), text=None):
	"""Profil als Diagramm fuer den Inhaltsbereich (800 x 268)."""
	x0, y0, x1, y1 = Oberflaeche.INHALT
	b = np.full((y1 - y0, x1 - x0, 3), 255, np.uint8)
	h = b.shape[0] - 10
	for p in (0.25, 0.5, 0.75):
		cv2.line(b, (0, int(h - p * h) + 5), (W, int(h - p * h) + 5), (225, 225, 225), 1)
	xs = np.linspace(0, W - 1, len(profil))
	skala = 240.0 / max(float(np.max(profil)), 60.0)  # schwache Signale sichtbar machen, Rauschen nicht aufblasen
	ys = h - np.clip(np.asarray(profil) * skala, 0, 255) / 255.0 * h + 5
	cv2.polylines(b, [np.stack([xs, ys], 1).astype(np.int32)], False, farbe, 2, cv2.LINE_AA)
	if marke is not None:
		x = int(marke * (W - 1) / (len(profil) - 1))
		cv2.line(b, (x, 0), (x, b.shape[0]), (0, 0, 220), 2)
	if text:
		cv2.putText(b, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 180), 2, cv2.LINE_AA)
	return b


def planck(wl_nm, t):
	wl = np.asarray(wl_nm, dtype=float) * 1e-9
	return wl ** -5 / (np.exp(C2 / (wl * t)) - 1.0)


# --------------------------------------------------------------------------- Schritte
def schritt_ausschnitt(ui):
	"""Spektrum im vollen Sensorbild finden und 4:3-Ausschnitt vorschlagen."""
	cam = kamera.kamera_starten(5000, 4.0, 1050000, crop="voll")
	bel = Belichtung(cam, stufe=5)
	vorschlag = None
	try:
		while True:
			f = bel.bild(False)  # Vollbild (VOLL_W x VOLL_H), ungespiegelt (Sensorkoordinaten)
			fx = SENSOR_W / f.shape[1]  # OV5647: 2 (halbe Aufloesung), OV9281: 1
			hell = f.max(axis=2).astype(float)
			spitze = np.percentile(hell, 99.8)
			# 10 % statt 30 % der Spitze: auch die schwachen Enden zaehlen (02.10.: Rot wurde abgeschnitten)
			sockel = np.percentile(hell, 20)
			maske = hell > sockel + 0.1 * max(spitze - sockel, 1)
			# Zusammenhaengende Gebiete (Luecken bis 2 % der Bildbreite ueberbrueckt) bilden und das
			# mit der groessten Gesamthelligkeit nehmen. 02.10.: Reflex neben dem Band -> nur Band um die
			# hellste Spalte; 03.10.: ein schmaler, sehr heller Fleck (Spaltlicht/Reflex) war heller als
			# das Band und wurde gewaehlt -> jetzt zaehlt die Summe ueber die ganze Breite.
			belegt = maske.sum(axis=0) > 3
			spalten = np.array([], dtype=int)
			if belegt.any():
				luecke = max(3, int(0.02 * f.shape[1]))
				idx = np.where(belegt)[0]
				gebiete, start = [], idx[0]
				for v, w in zip(idx[:-1], idx[1:]):
					if w - v > luecke:
						gebiete.append((start, v)); start = w
				gebiete.append((start, idx[-1]))
				licht = np.where(maske, hell, 0).sum(axis=0)
				ga, gb = max(gebiete, key=lambda g: licht[g[0]:g[1] + 1].sum())
				spalten = idx[(idx >= ga) & (idx <= gb)]
			vorschlag = None
			zu_breit = len(spalten) > 0.8 * f.shape[1]
			if len(spalten) > 20 and not zu_breit:
				xa, xb = spalten.min(), spalten.max()
				zeilen = np.where(maske[:, xa:xb + 1].sum(axis=1) > 3)[0]
				if len(zeilen) > 5:
					ya, yb = zeilen.min(), zeilen.max()
					# in Sensorkoordinaten, Rand je Seite, Hoehe = 3/4 Breite, Bandmitte mittig
					xa, xb, ya, yb = fx * xa, fx * xb, fx * ya, fx * yb
					rand = 0.149 * (xb - xa)  # je Seite ~15 %: Rahmen = 1,3 x Spektrum (27.09.: nochmals 10 % breiter)
					cw = min(int(round((xb - xa + 2 * rand) / 4)) * 4, SENSOR_W)
					ch = cw * 3 // 4
					if ch > SENSOR_H:
						ch = SENSOR_H // 4 * 4
						cw = ch * 4 // 3
					cx = int(np.clip(xa - rand, 0, SENSOR_W - cw))
					cy = int(np.clip((ya + yb) / 2 - ch / 2, 0, SENSOR_H - ch))
					vorschlag = (int(cx) & ~1, int(cy) & ~1, int(cw), int(ch))
			# Vorschau: Kamerabild mit erkanntem Rahmen
			vh = min(268, int(round(357 * SENSOR_H / SENSOR_W)))
			vorschau = np.zeros((268, 357, 3), np.uint8)
			vorschau[(268 - vh) // 2:(268 - vh) // 2 + vh] = cv2.resize(f, (357, vh))
			if vorschlag:
				s = 357 / SENSOR_W
				cx, cy, cw, ch = vorschlag
				oy = (268 - vh) // 2
				cv2.rectangle(vorschau, (int(cx * s), oy + int(cy * s)), (int((cx + cw) * s), oy + int((cy + ch) * s)), (0, 255, 0), 2)
			inhalt = np.full((268, W, 3), 30, np.uint8)
			inhalt[:, 221:578] = vorschau
			if zu_breit:
				info = "Fast das ganze Bild ist hell – dunkler schalten oder Raumlicht abschirmen"
			elif vorschlag:
				info = "Erkannt: x %d, y %d, %d x %d Pixel" % vorschlag
			else:
				info = "Kein Spektrum erkannt"
			ui.zeigen("Schritt 1 von 6: Bildausschnitt",
			          ["Weißes Licht (LED-Lampe oder Handylicht) vor den Spalt halten.",
			           "Der grüne Rahmen zeigt den erkannten Spektrumbereich.",
			           bel.text(spitze), info],
			          inhalt, [("abbruch", "Abbrechen", "rot"), ("dunkler", "Dunkler", "blau"), ("heller", "Heller", "blau"),
			                   ("ok", "Übernehmen", "gruen" if vorschlag else "grau")])
			t = ui.taste()
			bel.taste(t)
			if t == "abbruch":
				return None
			if t == "ok" and vorschlag:
				return vorschlag
	finally:
		cam.stop()
		cam.close()


def schritt_laser(ui, cam, bel, nummer, name, wellenlaenge, spiegeln):
	"""Laserlinie live anzeigen, Wellenlaenge einstellbar, auf 'Messen' 15 Bilder mitteln."""
	while True:
		p, aus = messen(bel, spiegeln)
		px, hoehe = linie_finden(p)
		messbar = px is not None and aus < 245
		text = ("Linie bei %.1f px" % px) if px is not None else "keine Linie erkannt"
		ui.zeigen("Schritt %d von 6: %s" % (nummer, name),
		          ["%s aufs Butterbrotpapier vor dem Spalt richten. Nicht ins Okular schauen!" % name,
		           "Belichtung mit Dunkler/Heller so wählen, dass die Spitze \"gut\" ist.",
		           bel.text(aus),
		           "Wellenlänge: %d nm  (− / +)      %s" % (wellenlaenge, text)],
		          profil_bild(p, px, text=text),
		          [("abbruch", "Abbrechen", "rot"), ("dunkler", "Dunkler", "blau"), ("heller", "Heller", "blau"),
		           ("minus", "− 1 nm", "grau"), ("plus", "+ 1 nm", "grau"),
		           ("messen", "Messen", "gruen" if messbar else "grau")])
		t = ui.taste()
		bel.taste(t)
		if t == "abbruch":
			return None
		if t == "minus":
			wellenlaenge -= 1
		if t == "plus":
			wellenlaenge += 1
		if t == "messen" and messbar:
			werte = []
			for _ in range(40):
				p, aus = messen(bel, spiegeln)
				m, _ = linie_finden(p)
				if m is not None and aus < 250:
					werte.append(m)
				if len(werte) >= 15:
					break
			if len(werte) < 5:
				continue  # zu wenig gueltige Bilder, weiter live
			mittel, streu = float(np.mean(werte)), float(np.std(werte))
			ui.zeigen("Schritt %d von 6: %s" % (nummer, name),
			          ["Gemessen: %.1f px (Streuung %.1f px) aus %d Bildern" % (mittel, streu, len(werte)),
			           "Zugeordnet: %d nm" % wellenlaenge, "Übernehmen oder neu messen?"],
			          profil_bild(p, mittel, text="%.1f px = %d nm" % (mittel, wellenlaenge)),
			          [("nochmal", "Nochmal", "grau"), ("weiter", "Weiter", "gruen")])
			while True:
				t = ui.taste()
				if t == "weiter":
					return mittel, wellenlaenge, streu
				if t == "nochmal":
					break
				cv2.waitKey(30)


def spitze_finden(profil, bis_px):
	"""Breite Spitze (z. B. LED-Blau) links von bis_px: (Position mit Subpixel, Hoehe) oder (None, 0)."""
	glatt = np.convolve(profil, np.ones(9) / 9, mode="same")
	bereich = glatt[:max(10, int(bis_px) - 20)]
	i = int(np.argmax(bereich))
	hoehe = bereich[i] - float(np.median(profil))
	if hoehe < 10 or i < 2 or i > len(bereich) - 3:
		return None, 0.0
	a, b, c = glatt[i - 1], glatt[i], glatt[i + 1]
	kruemmung = a - 2 * b + c
	versatz = 0.5 * (a - c) / kruemmung if kruemmung != 0 else 0.0
	return i + float(np.clip(versatz, -1, 1)), hoehe


def schritt_blau(ui, cam, bel, spiegeln, gruen_px):
	"""Optionaler dritter Punkt im Blauen. Rueckgabe (px, nm, streuung), "auslassen" oder None (Abbruch)."""
	wellenlaenge = 450
	while True:
		p, aus = messen(bel, spiegeln)
		px, hoehe = spitze_finden(p, gruen_px)
		messbar = px is not None and aus < 245
		text = ("Spitze bei %.1f px" % px) if px is not None else "keine Spitze links vom Grün"
		ui.zeigen("Schritt 4 von 6: Blauer Punkt (optional)",
		          ["Weiße LED (Handylicht) vor den Spalt: die Blauspitze liegt bei ca. 450 nm.",
		           "Ohne 3. Punkt bleibt die Zuordnung linear und ist im Blauen ungenau.",
		           bel.text(aus),
		           "Wellenlänge: %d nm  (− / +)      %s" % (wellenlaenge, text)],
		          profil_bild(p, px, farbe=(200, 60, 0), text=text),
		          [("abbruch", "Abbrechen", "rot"), ("auslassen", "Auslassen", "grau"),
		           ("dunkler", "Dunkler", "blau"), ("heller", "Heller", "blau"),
		           ("minus", "− 1 nm", "grau"), ("plus", "+ 1 nm", "grau"),
		           ("messen", "Messen", "gruen" if messbar else "grau")])
		t = ui.taste()
		bel.taste(t)
		if t == "abbruch":
			return None
		if t == "auslassen":
			return "auslassen"
		if t == "minus":
			wellenlaenge -= 1
		if t == "plus":
			wellenlaenge += 1
		if t == "messen" and messbar:
			werte = []
			for _ in range(30):
				p, aus = messen(bel, spiegeln)
				m, _ = spitze_finden(p, gruen_px)
				if m is not None and aus < 250:
					werte.append(m)
				if len(werte) >= 15:
					break
			if len(werte) < 5:
				continue
			mittel, streu = float(np.mean(werte)), float(np.std(werte))
			ui.zeigen("Schritt 4 von 6: Blauer Punkt (optional)",
			          ["Gemessen: %.1f px (Streuung %.1f px) aus %d Bildern" % (mittel, streu, len(werte)),
			           "Zugeordnet: %d nm" % wellenlaenge, "Übernehmen oder neu messen?"],
			          profil_bild(p, mittel, farbe=(200, 60, 0), text="%.1f px = %d nm" % (mittel, wellenlaenge)),
			          [("nochmal", "Nochmal", "grau"), ("weiter", "Weiter", "gruen")])
			while True:
				t = ui.taste()
				if t == "weiter":
					return mittel, wellenlaenge, streu
				if t == "nochmal":
					break
				cv2.waitKey(30)


def zuordnung(punkte):
	"""Wellenlaenge je Pixel aus den Kalibrierpunkten: linear (2) bzw. Polynom 2. Grades (3)."""
	from specFunctions import zuordnung_berechnen
	return zuordnung_berechnen([p[0] for p in punkte], [p[1] for p in punkte], kamera.FRAME_W)[0]


ZIEL = 200  # Ziel-Aussteuerung des hellsten Farbkanals bei der automatischen Belichtung
TITEL_GL = "Schritt 5 von 6: Glühlampe (Normkurve)"


def messen_spalten(bel, spiegeln):
	"""Ein Bild: (Messprofil = Mittel der Farbkanaele, hellster Kanal je Spalte)."""
	f = bel.bild(spiegeln)
	return kamera.zeilenprofil(f), kamera.kanalmaximum(f)


def einregeln(ui, bel, spiegeln, spalten, text):
	"""Belichtung automatisch so waehlen, dass der hellste Kanal in `spalten` bei ~ZIEL liegt.
	Rueckgabe: True (fertig), None (Abbruch)."""
	for runde in range(12):
		p, km = messen_spalten(bel, spiegeln)
		sockel = float(np.percentile(km, 3))
		ist = float(km[spalten].max())
		ui.zeigen(TITEL_GL, [text, "Belichtung wird eingeregelt … %.1f ms · Spitze %d (Ziel %d)" % (bel.us / 1000, ist, ZIEL)],
		          profil_bild(p, farbe=(0, 90, 200)), [("abbruch", "Abbrechen", "rot")])
		if ui.taste() == "abbruch":
			return None
		if 170 <= ist <= 230:
			return True
		if ist < 170 and bel.us >= STUFEN_US[-1]:
			return True  # Anschlag 1 s: mit dem arbeiten, was da ist
		if ist > 230 and bel.us <= STUFEN_US[0]:
			return True
		if ist >= 250:
			neu = bel.us * 0.4  # uebersteuert: wahres Verhaeltnis unbekannt, kraeftig verkuerzen
		else:
			neu = bel.us * (ZIEL - sockel) / max(ist - sockel, 2.0)
		bel.frei_setzen(neu)
	return True


def mitteln(ui, bel, spiegeln, text):
	"""Mittelwert des Profils + hoechster Kanalwert je Spalte ueber alle Bilder (fuer Uebersteuerung)."""
	n = int(min(60, max(15, 20e6 / bel.us)))  # bei langen Zeiten weniger Bilder (1 s -> 20 Bilder)
	summe = np.zeros(kamera.FRAME_W)
	kmax = np.zeros(kamera.FRAME_W)
	for k in range(n):
		p, km = messen_spalten(bel, spiegeln)
		summe += p
		kmax = np.maximum(kmax, km)
		if k % 5 == 0:
			ui.zeigen(TITEL_GL, [text, "Messe … %d von %d Bildern (%.1f ms)" % (k, n, bel.us / 1000)], None, [])
	return summe / n, kmax


def gluehlampe_zusammensetzen(kurz, us_kurz, lang, us_lang, kmax_lang):
	"""Zwei Messungen zu einem Profil (Einheit: Zaehlwerte der langen Belichtung).

	Lang (Blau gut ausgesteuert, Rot darf uebersteuern) wird ueberall genommen, wo es
	nicht uebersteuert ist; sonst die kurze Messung, hochgerechnet mit dem Zeitverhaeltnis
	und in der Ueberlappung an die lange Messung angeglichen (keine Stufe)."""
	sk = np.clip(kurz - np.percentile(kurz, 3), 0, None)
	sl = np.clip(lang - np.percentile(lang, 3), 0, None)
	zu_hell = kmax_lang >= 240
	# Nachbarn uebersteuerter Spalten ebenfalls meiden (Ueberstrahlen)
	zu_hell = np.convolve(zu_hell.astype(float), np.ones(9), mode="same") > 0
	hoch = sk * (us_lang / us_kurz)
	# Ueberlappung: beide nicht uebersteuert und kurz sicher ueber dem Rauschen (Rohdaten,
	# 8-Bit-Skala). Frueher > 20 -> es gab nie Ueberlappung, Verhaeltnis blieb 1,0 (28.09.)
	beide = ~zu_hell & (sk > 3)
	verhaeltnis = float(np.median(sl[beide] / hoch[beide])) if beide.sum() >= 10 else 1.0
	hoch *= verhaeltnis
	return np.where(zu_hell, hoch, sl), verhaeltnis, int(zu_hell.sum())


def schritt_gluehlampe(ui, cam, bel, spiegeln, wl):
	"""Gluehlampe als Planck-Strahler: Korrekturfaktor je Wellenlaenge.

	Zwei Messungen mit automatisch gewaehlter Belichtung: kurz (nirgends uebersteuert,
	liefert Rot) und lang (Blau gut ausgesteuert). Eine Gluehlampe hat bei 420 nm nur
	wenige Prozent ihrer Rot-Intensitaet; mit einer einzigen Belichtung lag Blau nur
	2-3 Zaehlwerte ueber dem Sockel (27.09.)."""
	temperatur = 2500  # 100-W-Gluehlampe: per Abgleich auf LED 5000 K bestimmt (02.10.: 2506 K, vorher 2850 angenommen)
	blau = np.where(wl <= 480)[0]
	if len(blau) < 10:
		blau = np.arange(kamera.FRAME_W // 4)
	alle = np.arange(kamera.FRAME_W)
	while True:
		p, km = messen_spalten(bel, spiegeln)
		aus = float(km.max())
		# Live-Vorschau grob nachfuehren, damit die Kurve sichtbar bleibt
		if aus >= 250:
			bel.frei_setzen(bel.us * 0.5)
		elif aus < 100:
			bel.frei_setzen(bel.us * 1.6)
		ui.zeigen(TITEL_GL,
		          ["Glühlampe (100 W, OHNE Dimmer) mit 15–20 cm Abstand. Achtung, heiß!",
		           "Die Belichtung wird automatisch gewählt: 2 Messungen (kurz für Rot, lang für Blau).",
		           "Vorschau %.1f ms · Spitze %d" % (bel.us / 1000, aus),
		           "Farbtemperatur der Lampe: %d K  (− / +)" % temperatur],
		          profil_bild(p, farbe=(0, 90, 200)),
		          [("abbruch", "Abbrechen", "rot"), ("minus", "− 50 K", "grau"), ("plus", "+ 50 K", "grau"),
		           ("messen", "Messen", "gruen" if aus > 30 else "grau")])
		t = ui.taste()
		if t == "abbruch":
			return None
		if t == "minus":
			temperatur -= 50
		if t == "plus":
			temperatur += 50
		if t != "messen" or aus <= 30:
			continue

		# 1) kurz: gesamtes Spektrum nirgends uebersteuert
		if einregeln(ui, bel, spiegeln, alle, "Messung 1 von 2 (kurz, für Rot)") is None:
			return None
		kurz, kmax_kurz = mitteln(ui, bel, spiegeln, "Messung 1 von 2 (kurz, für Rot)")
		us_kurz = bel.us
		if kmax_kurz.max() >= 250:
			continue  # doch uebersteuert (Lampe bewegt?) -> wieder live
		# 2) lang: blauer Teil gut ausgesteuert, Rot darf uebersteuern
		if einregeln(ui, bel, spiegeln, blau, "Messung 2 von 2 (lang, für Blau)") is None:
			return None
		lang, kmax_lang = mitteln(ui, bel, spiegeln, "Messung 2 von 2 (lang, für Blau)")
		us_lang = bel.us
		bel.frei_setzen(us_kurz)  # Vorschau wieder auf die kurze Zeit

		gemessen, verhaeltnis, n_hell = gluehlampe_zusammensetzen(kurz, us_kurz, lang, us_lang, kmax_lang)
		signal, gueltig, faktor, bereich = faktor_berechnen(gemessen, wl, temperatur, relativ=0.005)
		korrigiert = signal * faktor
		ansicht = profil_bild(korrigiert / max(korrigiert.max(), 1e-9) * 240, farbe=(0, 0, 0),
		                      text="korrigiert: %.0f-%.0f nm gueltig" % bereich)
		# Soll-Kurve (Planck) zum Vergleich einzeichnen
		soll = planck(wl, temperatur)
		soll = soll / soll[gueltig].max() * 240
		hh = ansicht.shape[0] - 10
		pts = [(int(i * (W - 1) / (len(wl) - 1)), int(hh - v / 255 * hh + 5)) for i, v in enumerate(soll) if gueltig[i]]
		if len(pts) > 1:
			cv2.polylines(ansicht, [np.array(pts, np.int32)], False, (0, 140, 255), 2, cv2.LINE_AA)
		passt = 0.8 <= verhaeltnis <= 1.25
		ui.zeigen(TITEL_GL,
		          ["Schwarz: korrigierte Messung, orange: Planck %d K – sollen deckungsgleich sein." % temperatur,
		           "Gültiger Bereich %.0f–%.0f nm." % bereich,
		           "Kurz %.1f ms · lang %.1f ms (×%.1f) · %d Spalten aus der kurzen Messung" % (us_kurz / 1000, us_lang / 1000, us_lang / us_kurz, n_hell),
		           "Übereinstimmung lang/kurz: %.2f %s" % (verhaeltnis, "(gut)" if passt else "– AUFFÄLLIG, besser nochmal messen")],
		          ansicht, [("nochmal", "Nochmal", "grau"), ("weiter", "Weiter", "gruen")])
		while True:
			t = ui.taste()
			if t == "weiter":
				return {"temperatur": temperatur, "faktor": faktor, "bereich": bereich,
				        "belichtung_us": us_kurz, "belichtung_lang_us": us_lang, "verhaeltnis": verhaeltnis,
				        "gemessen": gemessen, "kurz": kurz, "lang": lang}
			if t == "nochmal":
				break
			cv2.waitKey(30)


GLAETTUNG_MIN_NM = 3.0   # Glaettung der Korrektur innen ...
GLAETTUNG_MAX_NM = 12.0  # ... und an den Raendern (Gauss-Sigma in nm)
KANTE_NM = 15.0     # Fenster fuer die Kantenerkennung
KANTE_ABFALL = 0.5  # Empfindlichkeit < 50 % des Werts der letzten 15 nm -> Bildfeldrand
FAKTOR_MAX = 4.0  # staerkere Korrektur ist Rand-/Vignettierungseffekt, keine Kameraempfindlichkeit


def faktor_berechnen(gemessen, wl, temperatur, relativ=0.015):
	"""Korrekturfaktor je Pixel aus dem gemittelten Gluehlampen-Profil.

	Gueltig ist der zusammenhaengende Bereich um die Spitze, in dem das Signal
	deutlich ueber dem Dunkelsockel liegt. Eine rein relative Schwelle (frueher 6 %
	der Spitze) warf bei starker Rotspitze das ganze Blau weg (27.09.: erst ab 504 nm).
	Nach 60 Bildern Mittelung ist das Rauschen < 0,2 Zaehlwerte, 1 Zaehlwert reicht.
	"""
	signal = np.clip(gemessen - np.percentile(gemessen, 3), 0, None)
	ueber = signal > max(relativ * signal.max(), 1.0)
	# nur der zusammenhaengende Bereich, der die Spitze enthaelt (keine Rauschinseln)
	i = int(np.argmax(signal))
	a = i
	while a > 0 and ueber[a - 1]:
		a -= 1
	b = i
	while b < len(signal) - 1 and ueber[b + 1]:
		b += 1
	gueltig = np.zeros_like(ueber)
	gueltig[a:b + 1] = True
	faktor = np.zeros_like(signal)
	faktor[gueltig] = planck(wl[gueltig], temperatur) / signal[gueltig]
	kern = np.ones(15) / 15
	glatt = np.convolve(np.where(gueltig, faktor, 0), kern, mode="same")
	gewicht = np.convolve(gueltig.astype(float), kern, mode="same")
	faktor = np.where(gueltig, glatt / np.maximum(gewicht, 1e-9), 0.0)
	bezug = 560.0 if wl[gueltig].min() <= 560 <= wl[gueltig].max() else float(np.median(wl[gueltig]))
	faktor /= np.interp(bezug, wl, faktor)
	# An den Enden faellt das Signal durch die Vignettierung steil ab; der Faktor
	# wuerde dort die Kante "hochziehen" (27.09.: x9,5 bei 660 nm -> rote Wand).
	# Gueltig bleibt nur der zusammenhaengende Bereich um den Bezug mit Faktor <= FAKTOR_MAX.
	i = int(np.argmin(np.abs(wl - bezug)))
	ok = gueltig & (faktor <= FAKTOR_MAX)
	a = i
	while a > 0 and ok[a - 1]:
		a -= 1
	b = i
	while b < len(ok) - 1 and ok[b + 1]:
		b += 1
	# Steile Kante abschneiden (Blende/Vignettierung): Faellt die Empfindlichkeit
	# (1/Faktor) innerhalb von 15 nm auf unter die Haelfte, ist das keine
	# Kameraeigenschaft, sondern der Rand des Bildfelds. Dort misst eine LED nur
	# noch Streulicht, das die Korrektur hochziehen wuerde (28.09.: Rot am Rand).
	empf = np.where(faktor[a:b + 1] > 0, 1.0 / np.maximum(faktor[a:b + 1], 1e-9), 0.0)
	wl_ab = wl[a:b + 1]
	mitte = i - a
	def kante(richtung):
		k = mitte
		while 0 <= k + richtung < len(empf):
			innen = np.abs(wl_ab - wl_ab[k + richtung]) <= KANTE_NM
			innen &= (np.arange(len(empf)) - (k + richtung)) * richtung < 0  # nur Richtung Mitte
			if empf[k + richtung] < KANTE_ABFALL * empf[innen].max():
				break
			k += richtung
		return k
	lo, hi = a + kante(-1), a + kante(1)
	gueltig = np.zeros_like(gueltig)
	gueltig[lo:hi + 1] = True
	faktor = np.where(gueltig, faktor, 0.0)
	faktor = faktor_glaetten(wl, faktor, bezug)
	bereich = (float(wl[gueltig].min()), float(wl[gueltig].max()))
	return signal, gueltig, faktor, bereich


def faktor_glaetten(wl, faktor, bezug=560.0):
	"""Korrekturfaktor zusaetzlich glaetten, an den Enden staerker (02.10.: am roten Rand
	ab ~760 nm wurde die Kurve unruhig, der Faktor steigt dort bis ~3,4 und verstaerkt jede
	Welligkeit). Gauss in nm, im Log-Bereich (Faktoren sind Verhaeltnisse), randgerecht
	lokal linear angepasst (kein Abflachen am Ende). Breite: 3 nm innen, bis 12 nm am Rand."""
	wl = np.asarray(wl, dtype=float)
	ok = faktor > 0
	if ok.sum() < 5:
		return faktor
	w, lf = wl[ok], np.log(faktor[ok])
	lo, hi = w.min(), w.max()
	abstand = np.minimum(w - lo, hi - w)            # nm bis zum naechsten Rand
	sigma = np.clip(12.0 - abstand * (9.0 / 40.0), GLAETTUNG_MIN_NM, GLAETTUNG_MAX_NM)
	d = w[None, :] - w[:, None]
	g = np.exp(-0.5 * (d / sigma[:, None]) ** 2)
	# lokale Gerade statt Mittelwert: kein Abflachen des steilen Anstiegs am Rand
	s0, s1, s2 = g.sum(1), (g * d).sum(1), (g * d * d).sum(1)
	t0, t1 = (g * lf[None, :]).sum(1), (g * d * lf[None, :]).sum(1)
	glatt = (s2 * t0 - s1 * t1) / np.maximum(s0 * s2 - s1 * s1, 1e-12)
	ergebnis = np.zeros_like(faktor)
	ergebnis[ok] = np.exp(glatt)
	return ergebnis / np.interp(bezug, wl[ok], ergebnis[ok])


def speichern(crop, spiegeln, punkte, gluehlampe, wl):
	stempel = time.strftime("%Y%m%d-%H%M%S")
	sicherung = os.path.join(ORDNER, "alt", stempel)
	os.makedirs(sicherung, exist_ok=True)
	for datei in ("kamera_einstellungen.json", "caldata.txt", "empfindlichkeit.csv"):
		pfad = os.path.join(ORDNER, datei)
		if os.path.exists(pfad):
			shutil.copy2(pfad, sicherung)
	with open(os.path.join(ORDNER, "kamera_einstellungen.json"), "w") as f:
		json.dump({"crop": list(crop), "spiegeln": spiegeln, "sensor": kamera.SENSOR, "stand": stempel}, f, indent=2)
	with open(os.path.join(ORDNER, "caldata.txt"), "w") as f:
		f.write(",".join("%.2f" % p[0] for p in punkte) + "\n")
		f.write(",".join("%.1f" % p[1] for p in punkte) + "\n")
	with open(os.path.join(ORDNER, "empfindlichkeit.csv"), "w") as f:
		f.write("Wellenlaenge_nm,Faktor\n")
		for w, k in zip(wl, gluehlampe["faktor"]):
			f.write("%.2f,%.6f\n" % (w, k))
	protokoll_pfad = os.path.join(ORDNER, "kalibrierung_protokoll.json")
	try:
		with open(protokoll_pfad) as f:
			protokoll = json.load(f)
	except (OSError, ValueError):
		protokoll = []
	protokoll.append({"zeit": stempel, "crop": list(crop), "spiegeln": spiegeln,
	                  "punkte": [{"px": p[0], "nm": p[1], "streuung_px": p[2]} for p in punkte],
	                  "gluehlampe_K": gluehlampe["temperatur"], "gueltig_nm": gluehlampe["bereich"],
	                  "belichtung_us": gluehlampe["belichtung_us"],
	                  "belichtung_lang_us": gluehlampe.get("belichtung_lang_us"),
	                  "verhaeltnis_lang_kurz": gluehlampe.get("verhaeltnis"),
	                  "gemessen": np.round(gluehlampe["gemessen"], 2).tolist(),
	                  "kurz": np.round(gluehlampe["kurz"], 2).tolist() if "kurz" in gluehlampe else None,
	                  "lang": np.round(gluehlampe["lang"], 2).tolist() if "lang" in gluehlampe else None})
	with open(protokoll_pfad, "w") as f:
		json.dump(protokoll, f)
	return sicherung


ACHSE_VON, ACHSE_BIS = 360.0, 800.0   # nach der Wellenlaengen-Kalibrierung auf diesen Bereich zuschneiden


def zuschnitt_berechnen(crop, spiegeln, punkte):
	"""Ausschnitt so verkleinern, dass ACHSE_VON..ACHSE_BIS die volle Bildbreite fuellt.
	Schritt 1 waehlt den Rahmen bewusst grosszuegig (u. a. Gluehlampen-IR bis ueber 850 nm);
	nach den Lasern/der LED ist die Zuordnung bekannt und der sinnvolle Bereich berechenbar.
	Rueckgabe: (neuer Ausschnitt, Funktion alte Bildspalte -> neue Bildspalte) oder (None, None).
	Abbildung wie in kamera._roh_auswerten: Bildspalte x <-> Sensorspalte cx + (x + 0,5) * cw / 800
	(gespiegelt von rechts gezaehlt)."""
	breite = kamera.FRAME_W
	cx, cy, cw, ch = crop
	s_alt = cw / breite
	wl = zuordnung(punkte)
	x = np.arange(breite, dtype=float)
	pa, pb = float(np.interp(ACHSE_VON, wl, x)), float(np.interp(ACHSE_BIS, wl, x))

	def sensor(xm, cx_, s_):
		return cx_ + ((breite - xm - 0.5) if spiegeln else (xm + 0.5)) * s_

	sa, sb = sensor(pa, cx, s_alt), sensor(pb, cx, s_alt)
	lo, hi = min(sa, sb), max(sa, sb)
	nw = int(round((hi - lo) / 4)) * 4
	if nw >= cw or nw < 64:
		return None, None   # nichts zu verkleinern (oder unplausibel)
	nh = nw * 3 // 4
	if nh > SENSOR_H:
		nh = SENSOR_H // 4 * 4
		nw = nh * 4 // 3
	nx = int(np.clip(round(lo), 0, SENSOR_W - nw)) & ~1
	ny = int(np.clip(round(cy + ch / 2 - nh / 2), 0, SENSOR_H - nh)) & ~1
	s_neu = nw / breite

	def umrechnen(xm):
		rel = (sensor(xm, cx, s_alt) - nx) / s_neu
		return (breite - 0.5 - rel) if spiegeln else (rel - 0.5)

	return (nx, ny, nw, nh), umrechnen


def main():
	ui = Oberflaeche()
	ui.zeigen("Kalibrierung des Spektrometers",
	          ["Ablauf: 1 Ausschnitt · 2/3 Laser · 4 blauer Punkt · Zuschnitt (automatisch) · 5 Glühlampe · 6 Speichern",
	           "Bereitlegen: weiße LED (Handylicht), beide Laser, Glühlampe ohne Dimmer.",
	           "Erst im letzten Schritt wird gespeichert, Abbrechen ist jederzeit möglich."],
	          None, [("abbruch", "Abbrechen", "rot"), ("start", "Start", "gruen")])
	while True:
		t = ui.taste()
		if t == "abbruch":
			return 1
		if t == "start":
			break
		cv2.waitKey(30)

	crop = schritt_ausschnitt(ui)
	if crop is None:
		return 1

	spiegeln = kamera.SPIEGELN
	cam = kamera.kamera_starten(10000, 4.0, 1050000, crop=crop)
	bel = Belichtung(cam, stufe=6)
	try:
		gruen = schritt_laser(ui, cam, bel, 2, "Grüner Laser", 532, spiegeln)
		if gruen is None:
			return 1
		rot = schritt_laser(ui, cam, bel, 3, "Roter Laser", 650, spiegeln)
		if rot is None:
			return 1
		# Blau muss links liegen: liegt Rot links von Gruen, Spiegelung umkehren
		if rot[0] < gruen[0]:
			spiegeln = not spiegeln
			gruen = (kamera.FRAME_W - 1 - gruen[0],) + gruen[1:]
			rot = (kamera.FRAME_W - 1 - rot[0],) + rot[1:]
		if abs(rot[0] - gruen[0]) < 50:
			ui.zeigen("Fehler", ["Grüne und rote Linie liegen zu dicht beieinander (%.0f / %.0f px)." % (gruen[0], rot[0]),
			                     "Vermutlich wurde zweimal derselbe Laser gemessen. Bitte neu starten."], None,
			          [("ende", "Beenden", "rot")])
			while ui.taste() != "ende":
				cv2.waitKey(30)
			return 1
		punkte = [gruen, rot]
		blau_hinweis = "ohne blauen Punkt (linear)"
		blau = schritt_blau(ui, cam, bel, spiegeln, gruen[0])
		if blau is None:
			return 1
		if blau != "auslassen":
			versuch = sorted([blau, gruen, rot])
			wl_test = zuordnung(versuch)
			if np.all(np.diff(wl_test) > 0) and blau[0] < gruen[0]:
				punkte = versuch
				from specFunctions import zuordnung_berechnen
				art = zuordnung_berechnen([q[0] for q in versuch], [q[1] for q in versuch], kamera.FRAME_W)[1]
				blau_hinweis = "Blau %.1f px = %d nm (%s)" % (blau[0], blau[1], "gekrümmt" if art == "parabel" else "abschnittsweise linear")
			else:
				blau_hinweis = "blauer Punkt verworfen (%.1f px liegt nicht links von Grün %.1f px)" % (blau[0], gruen[0])
		# Bildausschnitt auf den sinnvollen Bereich zuschneiden (ersetzt zuschnitt.py)
		crop_neu, umrechnen = zuschnitt_berechnen(crop, spiegeln, punkte)
		zuschnitt_hinweis = "Ausschnitt unverändert"
		if crop_neu is not None:
			ui.zeigen("Bildausschnitt anpassen",
			          ["Wellenlängen sind bekannt: Der Ausschnitt wird auf %d–%d nm zugeschnitten," % (ACHSE_VON, ACHSE_BIS),
			           "damit dieser Bereich die volle Displaybreite nutzt.",
			           "Alt %d,%d %dx%d  →  neu %d,%d %dx%d" % (tuple(crop) + tuple(crop_neu)),
			           "Kamera startet neu …"], None, [])
			punkte = sorted((umrechnen(q[0]),) + tuple(q[1:]) for q in punkte)
			gruen = (umrechnen(gruen[0]),) + tuple(gruen[1:])
			rot = (umrechnen(rot[0]),) + tuple(rot[1:])
			if blau not in (None, "auslassen"):
				blau_hinweis = blau_hinweis.replace("%.1f px" % blau[0], "%.1f px" % umrechnen(blau[0]))
			stufe = bel.stufe
			cam.stop()
			cam.close()
			crop = crop_neu
			cam = kamera.kamera_starten(10000, 4.0, 1050000, crop=crop)
			bel = Belichtung(cam, stufe=stufe)
			zuschnitt_hinweis = "zugeschnitten auf %d–%d nm" % (ACHSE_VON, ACHSE_BIS)
		wl = zuordnung(punkte)
		steigung = (wl[-1] - wl[0]) / (kamera.FRAME_W - 1)

		gluehlampe = schritt_gluehlampe(ui, cam, bel, spiegeln, wl)
		if gluehlampe is None:
			return 1
	finally:
		cam.stop()
		cam.close()

	ui.zeigen("Schritt 6 von 6: Zusammenfassung",
	          ["Ausschnitt %d,%d  %dx%d   Spiegeln: %s · %s" % (tuple(crop) + ("ja" if spiegeln else "nein", zuschnitt_hinweis)),
	           "Grün %.1f px = %d nm · Rot %.1f px = %d nm · %s" % (gruen[0], gruen[1], rot[0], rot[1], blau_hinweis),
	           "Achse %.0f–%.0f nm (Ø %.3f nm/px) · Glühlampe %d K, gültig %.0f–%.0f nm" % (wl[0], wl[-1], steigung, gluehlampe["temperatur"], *gluehlampe["bereich"]),
	           "Speichern ersetzt die bisherige Kalibrierung (Sicherung in alt/)."],
	          None, [("verwerfen", "Verwerfen", "rot"), ("speichern", "Speichern", "gruen")])
	while True:
		t = ui.taste()
		if t == "verwerfen":
			return 1
		if t == "speichern":
			sicherung = speichern(crop, spiegeln, punkte, gluehlampe, wl)
			ui.zeigen("Kalibrierung gespeichert", ["Alte Dateien gesichert in:", sicherung,
			                                       "Das Spektrometer startet gleich neu."], None, [])
			time.sleep(2.5)
			return 0
		cv2.waitKey(30)


if __name__ == "__main__":
	code = 1
	try:
		code = main()
	finally:
		cv2.destroyAllWindows()
	sys.exit(code)
