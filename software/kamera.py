"""Gemeinsame Kameraeinstellungen fuer spektrometer.py und die Messskripte.

Alle Skripte muessen das Spektrum identisch aufnehmen, sonst passen
Wellenlaengenkalibrierung (caldata.txt) und Empfindlichkeitskorrektur
(empfindlichkeit.csv) nicht zusammen. Deshalb stehen die Werte nur hier.
"""
import json
import os

# Picamera2(tuning=...) schreibt das Tuning in eine Temp-Datei und setzt diese Variable.
# Kindprozesse (Kalibrier-Assistent, Neustart per execv) erben sie, die Datei ist dann
# aber schon geloescht -> libcamera kann die Kamera nicht anmelden ("No camera found").
# Seit kamera.py beim Import das Modell abfragt (02.10.), trat das sofort auf.
_t = os.environ.get("LIBCAMERA_RPI_TUNING_FILE")
if _t and not os.path.exists(_t):
	del os.environ["LIBCAMERA_RPI_TUNING_FILE"]

import cv2
import numpy as np
from picamera2 import Picamera2

FRAME_W, FRAME_H = 800, 600

# Unterstuetzte Sensoren (Modell wird beim Import erkannt, ohne die Kamera zu oeffnen).
# 02.10.2026: Umstieg von OV5647 (Farbe, mit IR-Sperrfilter) auf Arducam OV9281 Mono
# (ohne IR-Filter, M12) -> Spektrum ueber 650 nm, keine Bayer-Kanaluebergaenge.
SENSOREN = {
	"ov5647": {"groesse": (2592, 1944), "voll": (1296, 972), "roh": "SGBRG16",
	           "tuning": "ov5647.json", "farbe": True, "crop": (1180, 722, 480, 360), "zeilen": 8},
	"ov9281": {"groesse": (1280, 800), "voll": (1280, 800), "roh": "R16",
	           "tuning": "ov9281_mono.json", "farbe": False, "crop": (107, 0, 1066, 800),
	           "zeilen": 30},  # Band ~97 Zeilen hoch (02.10.) -> 60 Zeilen mitteln, Rauschen /2
}
try:
	SENSOR = Picamera2.global_camera_info()[0]["Model"]
except Exception:
	SENSOR = "ov5647"
if SENSOR not in SENSOREN:
	print("WARNUNG: unbekannter Sensor %r, verwende Einstellungen fuer ov5647" % SENSOR)
	SENSOR = "ov5647"
_S = SENSOREN[SENSOR]
SENSOR_W, SENSOR_H = _S["groesse"]
VOLL_W, VOLL_H = _S["voll"]   # Hauptbild im Assistenten-Schritt "Ausschnitt"
FARBE = _S["farbe"]

# Das Spektrum belegt nur einen Teil des Sensorbilds. Per ScalerCrop wird nur
# dieser Bereich (Sensorkoordinaten) auf 800x600 abgebildet, Seitenverhaeltnis 4:3.
# Die Bandmitte muss auf Zeile 300 liegen. Nach Objektivwechsel / Umbau neu bestimmen!
CROP = _S["crop"]              # Standardwert, bis der Assistent einen Ausschnitt speichert
SPIEGELN = True                # Spektrum laeuft im Kamerabild Rot->Blau; Achse: Blau links
FARBVERSTAERKUNG = (1.6, 1.6)  # fester Weissabgleich (rot, blau) - nur Farbsensor

# Der Kalibrier-Assistent (kalibrierung.py) speichert Ausschnitt und Spiegelung hier:
EINSTELLUNGEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kamera_einstellungen.json")
try:
	with open(EINSTELLUNGEN) as _f:
		_e = json.load(_f)
	_crop = tuple(int(v) for v in _e["crop"])
	# nur uebernehmen, wenn fuer diesen Sensor gespeichert und innerhalb des Sensors
	_passt = _e.get("sensor", SENSOR) == SENSOR and _crop[0] + _crop[2] <= SENSOR_W and _crop[1] + _crop[3] <= SENSOR_H
	if _passt:
		CROP = _crop
		SPIEGELN = bool(_e["spiegeln"])
	else:
		print("Hinweis: gespeicherter Ausschnitt gehoert nicht zu %s -> Standard, bitte neu kalibrieren" % SENSOR)
except (OSError, ValueError, KeyError):
	pass

# Linear statt Gamma: Die Bildverarbeitung legt normalerweise eine Gammakurve
# ueber das Bild (fuers Auge). Fuer Messungen (Empfindlichkeitskorrektur, CRI)
# muessen die Werte proportional zur Lichtmenge sein.
LINEAR = True

# Messprofil aus den Sensor-Rohdaten (28.09.): Die Bildverarbeitung des Pi ist bei
# schwachen Signalen stark nichtlinear (Farbmatrix mit negativen Anteilen, Rauschfilter,
# Randabschattungs-Korrektur, 8 Bit). Test mit LED 4 ms / 16 ms: Verhaeltnis 5..60 statt 4.
# Die Rohdaten (10 Bit, Bayer GBRG) sind linear; Schwarzwert laut Metadaten.
ROHDATEN = True
ROH_FORMAT = _S["roh"]    # 10-Bit-Werte linksbuendig in 16 Bit (Bayer GBRG bzw. Mono)
ROH_WEISS = 1023 << 6    # Saettigung im 16-Bit-Container
ROH_ZEILEN = _S["zeilen"]  # Sensorzeilen je Seite um die Bandmitte (OV5647: 16, OV9281: 60 gemittelt)
_letztes = (None, None, None)  # (id(bild), profil, kanalmaximum) des zuletzt geholten Bildes


def _tuning():
	tuning = Picamera2.load_tuning_file(_S["tuning"])
	if LINEAR:
		kontrast = Picamera2.find_tuning_algo(tuning, "rpi.contrast")
		if kontrast is not None:
			kontrast["ce_enable"] = 0
			kontrast["gamma_curve"] = [0, 0, 65535, 65535]
		else:
			print("WARNUNG: rpi.contrast nicht im Tuning gefunden, Gamma bleibt aktiv")
	return tuning


def kamera_starten(belichtung_us, gain, max_bilddauer_us=66666, crop=None):
	"""Kamera mit fester Belichtung, festem Weissabgleich und Zuschnitt starten.
	crop=None: gespeicherter Ausschnitt; "voll": ganzes Sensorbild (fuer den Assistenten)."""
	if crop is None:
		crop = CROP
	voll = crop == "voll"
	cam = Picamera2(tuning=_tuning())
	steuerung = {"FrameDurationLimits": (33333, max_bilddauer_us)}
	if not voll:
		steuerung["ScalerCrop"] = tuple(crop)
	roh = {"size": (SENSOR_W, SENSOR_H)}
	if ROHDATEN and not voll:
		roh["format"] = ROH_FORMAT
	cfg = cam.create_video_configuration(
		main={"format": "RGB888", "size": (VOLL_W, VOLL_H) if voll else (FRAME_W, FRAME_H)},
		raw=roh, controls=steuerung)
	cam.configure(cfg)
	cam.start()
	if not voll:
		cam.set_controls({"ScalerCrop": tuple(crop)})
	steuern = {"AeEnable": False, "ExposureTime": int(belichtung_us), "AnalogueGain": float(gain)}
	if "ColourGains" in cam.camera_controls:  # Mono-Sensor hat keinen Weissabgleich
		steuern.update({"AwbEnable": False, "ColourGains": FARBVERSTAERKUNG})
	cam.set_controls(steuern)
	return cam


def bild(cam, spiegeln=None):
	"""Ein Bild holen, bei Bedarf so spiegeln, dass Blau links liegt."""
	f = cam.capture_array()
	if spiegeln is None:
		spiegeln = SPIEGELN
	return cv2.flip(f, 1) if spiegeln else f


def bild_mit_daten(cam, spiegeln=None):
	"""Bild + Metadaten (u. a. tatsaechlich wirksame ExposureTime).

	Achtung: Eine neue Belichtung wirkt erst nach ca. 5-7 Bildern. Wer auf eine
	bestimmte Belichtung angewiesen ist, muss die Metadaten pruefen."""
	global _letztes
	anfrage = cam.capture_request()
	try:
		f = anfrage.make_array("main").copy()
		daten = anfrage.get_metadata()
		roh = None
		if ROHDATEN and f.shape[1] == FRAME_W and FRAME_W > 0:
			roh = _roh_auswerten(cam, anfrage.make_array("raw"), daten)
	finally:
		anfrage.release()
	if spiegeln is None:
		spiegeln = SPIEGELN
	f = cv2.flip(f, 1) if spiegeln else f
	if roh is not None:
		profil, kmax = roh
		if spiegeln:
			profil, kmax = profil[::-1].copy(), kmax[::-1].copy()
		_letztes = (id(f), profil, kmax)
	return f, daten


def _roh_auswerten(cam, roh, daten):
	"""Messprofil + hellster Kanal je Spalte aus dem Bayer-Rohbild, auf die 800 Spalten
	des Hauptbilds umgerechnet (gleiche Achse wie bisher, Kalibrierung bleibt gueltig).
	Werte in 8-Bit-Skala (0..255), Schwarzwert abgezogen, 255 = Sensor gesaettigt."""
	try:
		r16 = roh.view(np.uint16)
		hoehe, breite = r16.shape
		schwarz = float(np.mean(daten.get("SensorBlackLevels", (1024,))))
		mx, my, mbreite, mhoehe = cam.camera_controls["ScalerCrop"][1]  # ScalerCropMaximum
		sx, sy, sbreite, shoehe = daten.get("ScalerCrop", CROP)
		fx, fy = breite / mbreite, hoehe / mhoehe
		x0 = int((sx - mx) * fx) & ~1
		x1 = min(int((sx - mx + sbreite) * fx) & ~1, breite)
		ym = int((sy - my + shoehe / 2) * fy) & ~1
		blk = r16[ym - ROH_ZEILEN:ym + ROH_ZEILEN, x0:x1].astype(np.float32)
		skala = 255.0 / (ROH_WEISS - schwarz)
		if FARBE:
			# Bayer GBRG: Zeile 0 = G B G B ..., Zeile 1 = R G R G ...
			g1, b, r, g2 = blk[0::2, 0::2], blk[0::2, 1::2], blk[1::2, 0::2], blk[1::2, 1::2]
			mittel = (r.mean(0) + (g1.mean(0) + g2.mean(0)) / 2 + b.mean(0)) / 3
			spitze = np.maximum(np.maximum(g1, g2), np.maximum(r, b)).max(0)
			mitte = x0 + 2 * np.arange(len(mittel)) + 1.0   # Superpixel-Mitten
		else:
			# Mono: jedes Pixel misst direkt, keine Farbfilter
			mittel = blk.mean(0)
			spitze = blk.max(0)
			mitte = x0 + np.arange(len(mittel)) + 0.5
		profil_sp = (mittel - schwarz) * skala
		kmax_sp = (spitze - schwarz) * skala
		# Pixel-Mitten -> Spalten des Hauptbilds (ScalerCrop -> 800 px)
		x_haupt = (mitte / fx + mx - sx) / sbreite * FRAME_W - 0.5
		ziel = np.arange(FRAME_W)
		return np.interp(ziel, x_haupt, profil_sp), np.interp(ziel, x_haupt, kmax_sp)
	except Exception as e:
		print("Rohdaten-Auswertung fehlgeschlagen:", e, flush=True)
		return None


def belichtung_wirksam(daten, soll_us):
	"""True, wenn die Kamera die gewuenschte Belichtungszeit schon anwendet."""
	return abs(daten.get("ExposureTime", 0) - soll_us) <= max(60, 0.05 * soll_us)


def zeilenprofil(f, halbe_hoehe=1):
	"""Messwert je Spalte: Mittel der drei Farbkanaele (= Summe/3), gemittelt ueber
	2*halbe_hoehe+1 Zeilen der Bandmitte. Die Summe verlaeuft glatt ueber die
	Uebergaenge Blau/Gruen und Gruen/Rot (das Maximum bricht dort ein)."""
	if _letztes[0] == id(f):
		return _letztes[1]  # linear aus den Rohdaten
	m = f.shape[0] // 2
	return f[m - halbe_hoehe:m + halbe_hoehe + 1].astype(float).mean(axis=2).mean(axis=0)


def kanalmaximum(f, halbe_hoehe=1):
	"""Hellster Farbkanal je Spalte - nur fuer Aussteuerung/Uebersteuerungspruefung.
	(Im Mittelwert faellt ein einzelner uebersteuerter Kanal nicht auf.)"""
	if _letztes[0] == id(f):
		return _letztes[2]
	m = f.shape[0] // 2
	return f[m - halbe_hoehe:m + halbe_hoehe + 1].max(axis=2).max(axis=0).astype(float)
