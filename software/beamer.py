"""Hochaufgeloeste Beamer-Ansicht fuer spektrometer.py.

Das 3,5"-Display zeigt die Bedienoberflaeche (800x480, herunterskaliert).
Fuer Beamer/Monitor an HDMI wird hier eine eigene Grafik in der Aufloesung
des Ausgangs gezeichnet (max. 1920 px breit): grosse Schrift, Kennwerte gut
lesbar, keine Buttons. Bedient wird weiter am Touchdisplay.
"""
import glob
import json
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

MAX_BREITE = 1920
SCHRIFT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SCHRIFT_FETT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

_schriften = {}
_farbcache = {}


def _aktuelle_modi():
	"""Aktive Ausgaenge laut Desktop (wlr-randr): {"HDMI-A-1": (1920, 1080, x, y)}."""
	try:
		ausgabe = subprocess.run(["wlr-randr", "--json"], capture_output=True, text=True, timeout=3).stdout
		modi = {}
		for o in json.loads(ausgabe):
			for m in o.get("modes", []):
				if o.get("enabled") and m.get("current"):
					pos = o.get("position") or {}
					modi[o["name"]] = (m["width"], m["height"], pos.get("x", 0), pos.get("y", 0))
		return modi
	except (OSError, ValueError, subprocess.SubprocessError):
		return {}


def hdmi_ausgang():
	"""Erster angeschlossener UND im Desktop aktiver HDMI-Ausgang als
	(Name, Breite, Hoehe, x, y) oder None.

	Nur /sys ("connected") reicht nicht: Beim Anstecken richtet kanshi den Ausgang
	erst kurz danach ein. Ein zu frueh geoeffnetes Fenster landet sonst auf dem
	3,5"-Display. Breite/Hoehe = aktuelle Aufloesung (kanshi: 1920x1080)."""
	aktuell = _aktuelle_modi()
	for pfad in sorted(glob.glob("/sys/class/drm/card*-HDMI-A-*")):
		try:
			with open(pfad + "/status") as f:
				if f.read().strip() != "connected":
					continue
			with open(pfad + "/modes") as f:
				modi = f.read().split()
			w, h = (int(v) for v in modi[0].split("x")) if modi else (1920, 1080)
		except (OSError, ValueError):
			continue
		name = pfad.split("-", 1)[1]  # z. B. "HDMI-A-1"
		if name not in aktuell:
			continue  # angeschlossen, aber noch nicht eingerichtet
		return (name,) + tuple(aktuell[name])
	return None


def zeichengroesse(w, h):
	"""Aufloesung der Beamer-Grafik: Seitenverhaeltnis des Ausgangs, hoechstens MAX_BREITE breit."""
	if w > MAX_BREITE:
		h = round(h * MAX_BREITE / w)
		w = MAX_BREITE
	return w, h


def _schrift(groesse, fett=False):
	schluessel = (groesse, fett)
	if schluessel not in _schriften:
		_schriften[schluessel] = ImageFont.truetype(SCHRIFT_FETT if fett else SCHRIFT, groesse)
	return _schriften[schluessel]


def _spektralfarben(wellenlaengen, wavelength_to_rgb):
	"""BGR-Farbe je Datenpunkt (zwischengespeichert, solange die Kalibrierung gleich bleibt)."""
	schluessel = (len(wellenlaengen), round(wellenlaengen[0], 3), round(wellenlaengen[-1], 3))
	if schluessel not in _farbcache:
		_farbcache.clear()
		farben = []
		for wl in wellenlaengen:
			r, g, b = wavelength_to_rgb(round(wl))
			farben.append((b, g, r))
		_farbcache[schluessel] = np.array(farben, dtype=np.uint8)
	return _farbcache[schluessel]


def zeichnen(W, H, wellenlaengen, werte, streifen, maxima_idx, kennwerte, hinweise,
             status, meldung, kurvenart, wavelength_to_rgb, gueltig=None):
	"""Beamer-Bild (BGR, H x W) zeichnen.

	wellenlaengen/werte: je Datenpunkt (0..255, schon korrigiert/normiert)
	streifen: Kamerastreifen (BGR), maxima_idx: Datenpunkt-Indizes der Maxima
	kennwerte: dict mit ra/r9/cct oder None, hinweise: Liste von Strings
	"""
	s = W / 1920.0  # Massstab relativ zu Full-HD
	n = len(werte)
	wl = np.asarray(wellenlaengen, dtype=float)
	werte = np.asarray(werte, dtype=float)

	bild = np.full((H, W, 3), 255, dtype=np.uint8)
	rand = int(40 * s)
	kopf = int(140 * s)
	streifen_h = int(70 * s)
	gx0, gx1 = rand + int(95 * s), W - rand
	gy0 = kopf + streifen_h + int(55 * s)
	gy1 = H - int(95 * s)
	gw, gh = gx1 - gx0, gy1 - gy0

	# Kopfleiste
	bild[:kopf] = (45, 45, 45)
	# Kamerastreifen ueber dem Diagramm
	sy = kopf + int(15 * s)
	bild[sy:sy + streifen_h, gx0:gx1] = cv2.resize(streifen, (gw, streifen_h), interpolation=cv2.INTER_AREA)

	# Raster: alle 10 nm hell, alle 50 nm dunkel
	def x_von_wl(w):
		return gx0 + np.interp(w, wl, np.arange(n)) * (gw - 1) / (n - 1)

	for w10 in range(int(np.ceil(wl.min() / 10) * 10), int(wl.max()) + 1, 10):
		x = int(round(x_von_wl(w10)))
		farbe = (120, 120, 120) if w10 % 50 == 0 else (215, 215, 215)
		cv2.line(bild, (x, gy0), (x, gy1), farbe, max(1, int((2 if w10 % 50 == 0 else 1) * s)))
	for p in range(0, 101, 25):
		y = int(gy1 - p / 100 * gh)
		cv2.line(bild, (gx0, y), (gx1, y), (215, 215, 215), max(1, int(s)))

	# Spektralkurve: farbig gefuellt (vektorisiert) + schwarze Umrisslinie
	xi = np.linspace(0, n - 1, gw)
	yw = np.interp(xi, np.arange(n), werte)
	hoehe = np.clip(yw / 255.0 * gh, 0, gh)
	farben = _spektralfarben(wl, wavelength_to_rgb)[np.round(xi).astype(int)]
	if gueltig is not None:
		# ausserhalb des kalibrierten Bereichs grau (wie auf dem Display)
		farben = np.where(np.asarray(gueltig)[np.round(xi).astype(int)][:, None], farben, np.uint8(175))
	zeilen = np.arange(gh)[:, None]
	maske = zeilen >= (gh - hoehe)[None, :]
	flaeche = bild[gy0:gy1, gx0:gx1]
	flaeche[maske] = np.broadcast_to(farben[None, :, :], (gh, gw, 3))[maske]
	punkte = np.stack([gx0 + np.arange(gw), gy1 - hoehe], axis=1).astype(np.int32)
	cv2.polylines(bild, [punkte], False, (0, 0, 0), max(2, int(2 * s)), cv2.LINE_AA)
	cv2.rectangle(bild, (gx0, gy0), (gx1, gy1), (80, 80, 80), max(1, int(2 * s)))

	# Maxima: Fahne + Beschriftung (Text folgt unten mit PIL)
	marken = []
	for i in maxima_idx:
		x = int(gx0 + i * (gw - 1) / (n - 1))
		y = int(gy1 - np.clip(werte[i] / 255.0 * gh, 0, gh))
		cv2.line(bild, (x, y - int(8 * s)), (x, y - int(38 * s)), (0, 0, 0), max(2, int(2 * s)))
		marken.append((x, y - int(38 * s), "%.1f nm" % wl[i]))

	# Text mit PIL (Umlaute, Kantenglaettung)
	pil = Image.fromarray(cv2.cvtColor(bild, cv2.COLOR_BGR2RGB))
	d = ImageDraw.Draw(pil)
	d.text((rand, int(22 * s)), "Spektrometer", font=_schrift(int(58 * s), True), fill=(255, 255, 255))
	d.text((rand, int(96 * s)), status + ("   ·   " + meldung if meldung else ""),
	       font=_schrift(int(24 * s)), fill=(255, 220, 90))
	if kennwerte:
		text = "Ra %d    R9 %d    %d K" % (round(kennwerte["ra"]), round(kennwerte["r9"]), round(kennwerte["cct"], -1))
		f = _schrift(int(62 * s), True)
		d.text((W - rand - d.textlength(text, font=f), int(18 * s)), text, font=f, fill=(255, 255, 255))
		if hinweise:
			t2 = "Schätzwert: " + ", ".join(hinweise)
			f2 = _schrift(int(24 * s))
			d.text((W - rand - d.textlength(t2, font=f2), int(98 * s)), t2, font=f2, fill=(255, 140, 120))
	f_achse = _schrift(int(26 * s))
	for w50 in range(int(np.ceil(wl.min() / 50) * 50), int(wl.max()) + 1, 50):
		x = x_von_wl(w50)
		t = "%d" % w50
		d.text((x - d.textlength(t, font=f_achse) / 2, gy1 + int(10 * s)), t, font=f_achse, fill=(0, 0, 0))
	t = "Wellenlänge in nm"
	f_titel = _schrift(int(28 * s), True)
	d.text(((gx0 + gx1) / 2 - d.textlength(t, font=f_titel) / 2, gy1 + int(48 * s)), t, font=f_titel, fill=(0, 0, 0))
	for p in range(0, 101, 25):
		t = "%d %%" % p
		d.text((gx0 - int(12 * s) - d.textlength(t, font=f_achse), gy1 - p / 100 * gh - int(15 * s)), t, font=f_achse, fill=(0, 0, 0))
	d.text((gx0, gy0 - int(40 * s)), "relative spektrale Verteilung (" + kurvenart + ")",
	       font=_schrift(int(24 * s)), fill=(60, 60, 60))
	f_marke = _schrift(int(28 * s), True)
	for x, y, t in marken:
		b = d.textlength(t, font=f_marke)
		x0 = min(max(x - b / 2 - 8 * s, gx0), gx1 - b - 16 * s)
		d.rectangle([x0, y - 40 * s, x0 + b + 16 * s, y], fill=(255, 235, 60), outline=(0, 0, 0), width=max(1, int(2 * s)))
		d.text((x0 + 8 * s, y - 37 * s), t, font=f_marke, fill=(0, 0, 0))
	return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
