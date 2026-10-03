#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# GEAENDERTE DATEI (Apache-2.0, Abschnitt 4b)
# Basis: PySpectrometer2 von Les Wright (https://github.com/leswright1977/PySpectrometer2),
# Apache License 2.0. Geaendert 2026 von Johannes Roeding fuer das Projekt
# "Spektrometer fuer Leuchtmittel" (https://github.com/kleiner009/spektrometer):
# Touch-Bedienung, Messung aus Sensor-Rohdaten, Empfindlichkeitskorrektur,
# Ra/R9/CCT, Kalibrier-Assistent, Beamer-Ansicht, deutsche Oberflaeche.
# ---------------------------------------------------------------------------

'''
PySpectrometer2 Les Wright 2022
https://www.youtube.com/leslaboratory
https://github.com/leswright1977

This project is a follow on from: https://github.com/leswright1977/PySpectrometer 

This is a more advanced, but more flexible version of the original program. Tk Has been dropped as the GUI to allow fullscreen mode on Raspberry Pi systems and the iterface is designed to fit 800*480 screens, which seem to be a common resolutin for RPi LCD's, paving the way for the creation of a stand alone benchtop instrument.

Whats new:
Higher resolution (800px wide graph)
3 row pixel averaging of sensor data
Fullscreen option for the Spectrometer graph
3rd order polymonial fit of calibration data for accurate measurement.
Improved graph labelling
Labelled measurement cursors
Optional waterfall display for recording spectra changes over time.
Key Bindings for all operations

All old features have been kept, including peak hold, peak detect, Savitsky Golay filter, and the ability to save graphs as png and data as CSV.

For instructions please consult the readme!
'''


import cv2
import time
import numpy as np
from specFunctions import wavelength_to_rgb,savitzky_golay,peakIndexes,readcal,writecal,background,generateGraticule
import base64
import argparse
import os
import sys
import subprocess
import glob
import warnings
warnings.filterwarnings("ignore")  # colour-science meldet fehlendes SciPy/Matplotlib, wird nicht gebraucht
try:
	import colour  # colour-science, liegt im venv ~/Spektrometer/venv
	COLOUR_OK = True
except ImportError:
	COLOUR_OK = False
import kamera  # gemeinsame Kameraeinstellungen (Zuschnitt, Spiegeln, linear, Weissabgleich)
import beamer  # hochaufgeloeste Ansicht fuer Beamer/Monitor an HDMI

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--fullscreen", help="Fullscreen (Native 800*480)",action="store_true")
group.add_argument("--waterfall", help="Enable Waterfall (Windowed only)",action="store_true")
args = parser.parse_args()
dispFullscreen = False
dispWaterfall = False
if args.fullscreen:
	print("Fullscreen Spectrometer enabled")
	dispFullscreen = True
if args.waterfall:
	print("Waterfall display enabled")
	dispWaterfall = True
	
	

frameWidth = 800
frameHeight = 600

#need to spend more time at: https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
#but this will do for now!
#min and max microseconds per frame gives framerate.
#30fps (33333, 33333)
#25fps (40000, 40000)

picamGain = 4.0

# --- Anpassung Spektrometer (Johannes, 2026-09-25) ---------------------------
# Zuschnitt, Spiegeln, Weissabgleich und lineare Kennlinie stehen in kamera.py.
BELICHTUNG_US = 60000  # feste Belichtungszeit (Automatik aus), mit t/g Gain anpassen
GLAETTUNG_FENSTER = 21  # Savitzky-Golay-Fenster (ungerade), groesser = glatter
GLAETTUNG_ORDNUNG = 3   # Polynomgrad des Filters, kleiner = glatter
ZEITMITTEL = 0.6        # Anteil des alten Spektrums je Bild (0 = aus), beruhigt Flackern
ANZAHL_MAXIMA = 3       # so viele staerkste Maxima werden beschriftet
MIN_SIGNAL = 6          # unterhalb dieser Rohsignal-Hoehe wird die Kurve nicht normiert
picam2 = kamera.kamera_starten(BELICHTUNG_US, picamGain, max_bilddauer_us=1050000)  # Belichtung bis 1 s
belichtung_soll = BELICHTUNG_US  # wird automatisch nachgefuehrt (siehe Hauptschleife)

#Change analog gain
#picam2.set_controls({"AnalogueGain": 10.0}) #Default 1
#picam2.set_controls({"Brightness": 0.2}) #Default 0 range -1.0 to +1.0
#picam2.set_controls({"Contrast": 1.8}) #Default 1 range 0.0-32.0



title1 = 'PySpectrometer 2 - Spectrograph'
title2 = 'PySpectrometer 2 - Waterfall'
stackHeight = 320+80+80 #height of the displayed CV window (graph+preview+messages)

if dispWaterfall == True:
	#watefall first so spectrum is on top
	cv2.namedWindow(title2,cv2.WINDOW_GUI_NORMAL)
	cv2.resizeWindow(title2,frameWidth,stackHeight)
	cv2.moveWindow(title2,200,200);

if dispFullscreen == True:
	cv2.namedWindow(title1,cv2.WND_PROP_FULLSCREEN)
	cv2.setWindowProperty(title1,cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
else:
	cv2.namedWindow(title1,cv2.WINDOW_GUI_NORMAL)
	cv2.resizeWindow(title1,frameWidth,stackHeight)
	cv2.moveWindow(title1,0,0);

#settings for peak detect
savpoly = 7 #savgol filter polynomial max val 15
mindist = 50 #minumum distance between peaks max val 100
thresh = 20 #Threshold max val 100

calibrate = False

clickArray = [] 
cursorX = 0
cursorY = 0
# Buttonleiste statt Banner: (Name, x0, x1) in Bildkoordinaten, Hoehe 80 px
BUTTONS = [("speichern", 8, 168, "Speichern"), ("kalibrieren", 176, 346, "Kalibrieren"),
           ("auto", 354, 484, "Auto"), ("dunkler", 492, 562, "-"), ("heller", 570, 640, "+"),
           ("beenden", 648, 792, "Beenden")]
# Belichtung: Auto (Nachfuehrung) oder von Hand in festen Stufen
STUFEN_US = [100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000]
belichtung_auto = True
aussteuerung = 0  # hellster Kanal in der Bandmitte (fuer Uebersteuerungswarnung)
aktion = None

def handle_mouse(event,x,y,flags,param):
	global clickArray
	global cursorX
	global cursorY
	global aktion
	mouseYOffset = 160
	if event == cv2.EVENT_MOUSEMOVE:
		cursorX = x
		cursorY = y	
	if event == cv2.EVENT_LBUTTONDOWN:
		if y < 80:
			for name, x0, x1, _ in BUTTONS:
				if x0 <= x <= x1:
					aktion = name
			return
		mouseX = x
		mouseY = y-mouseYOffset
		clickArray.append([mouseX,mouseY])
#listen for click on plot window
cv2.setMouseCallback(title1,handle_mouse)


font=cv2.FONT_HERSHEY_SIMPLEX

intensity = [0] * frameWidth #array for intensity data...full of zeroes

holdpeaks = False #are we holding peaks?
measure = False #are we measuring?
recPixels = False #are we measuring pixels and recording clicks?


#messages
msg1 = ""
saveMsg = ""

#blank image for Waterfall
waterfall = np.zeros([320,frameWidth,3],dtype=np.uint8)
waterfall.fill(0) #fill black

#Go grab the computed calibration data
caldata = readcal(frameWidth)
wavelengthData = caldata[0]
calmsg1 = caldata[1]
calmsg2 = caldata[2]
calmsg3 = caldata[3]

#generate the craticule data
graticuleData = generateGraticule(wavelengthData)
tens = (graticuleData[0])
fifties = (graticuleData[1])

def usb_ziel():
	# erster beschreibbarer, eingehaengter USB-Stick (Desktop haengt unter /media/<user>/ ein)
	for d in sorted(glob.glob('/media/*/*')):
		if os.path.ismount(d) and os.access(d, os.W_OK):
			return d
	return None

def auf_usb_speichern(graph, maxima_nm):
	ziel = usb_ziel()
	if ziel is None:
		return "Kein USB-Stick gefunden!"
	jetzt = time.strftime("%Y-%m-%d %H:%M:%S")
	kopf = np.full([30, graph.shape[1], 3], 255, dtype=np.uint8)
	text = "Spektrum " + jetzt
	if maxima_nm:
		text += "   Maxima: " + ", ".join(str(w) + " nm" for w in maxima_nm)
	cv2.putText(kopf, text, (8, 20), font, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
	bild = np.vstack((kopf, graph))
	name = "spektrum-" + time.strftime("%Y%m%d-%H%M%S") + ".png"
	try:
		cv2.imwrite(os.path.join(ziel, name), bild)
		os.sync()  # sicher auf den Stick schreiben, bevor er abgezogen wird
	except Exception as e:
		print("Speichern fehlgeschlagen:", e)
		return "Speichern fehlgeschlagen!"
	return "Gespeichert: " + name

def buttonleiste(meldung):
	leiste = np.full([80, frameWidth, 3], 40, dtype=np.uint8)
	for name, x0, x1, beschriftung in BUTTONS:
		farbe = {"speichern": (60, 140, 60), "kalibrieren": (150, 100, 40),
		         "dunkler": (110, 80, 50), "heller": (110, 80, 50)}.get(name, (60, 60, 150))
		if name == "auto":
			beschriftung = "Auto" if belichtung_auto else "Manuell"
			farbe = (60, 140, 60) if belichtung_auto else (90, 90, 90)
		cv2.rectangle(leiste, (x0, 8), (x1, 72), farbe, -1)
		cv2.rectangle(leiste, (x0, 8), (x1, 72), (220, 220, 220), 2)
		gross = name in ("dunkler", "heller")
		(tw, th), _ = cv2.getTextSize(beschriftung, font, 1.6 if gross else 0.8, 3 if gross else 2)
		cv2.putText(leiste, beschriftung, (x0 + (x1 - x0 - tw) // 2, 40 + th // 2), font,
		            1.6 if gross else 0.8, (255, 255, 255), 3 if gross else 2, cv2.LINE_AA)
	return leiste

def status_einblenden(bild, meldung):
	"""Statuszeilen gross in den dunklen Kamerastreifen (Zeilen 80-160) schreiben."""
	ms = belichtung_soll / 1000
	kurve = "korrigiert" if EMPFINDLICHKEIT is not None else "unkorrigiert"
	zeile1 = [(calmsg1 + " | " + kurve, (0, 255, 255))]
	zeile2 = [("Bel. %s ms %s" % (("%.1f" % ms) if ms < 10 else "%d" % ms,
	                              "Auto" if belichtung_auto else "manuell"), (0, 255, 255))]
	if aussteuerung >= 250:
		zeile2.append(("  UEBERSTEUERT!", (60, 60, 255)))
	elif meldung:
		zeile2.append(("  " + ("Gespeichert" if meldung.startswith("Gespeichert") else meldung[:26]), (120, 255, 120)))
	# Hilfslinien liegen bei y 118/122: Zeile 1 darueber, Zeile 2 darunter
	for y, teile in ((108, zeile1), (150, zeile2)):
		x = 8
		for text, farbe in teile:
			cv2.putText(bild, text, (x, y), font, 0.8, (0, 0, 0), 5, cv2.LINE_AA)
			cv2.putText(bild, text, (x, y), font, 0.8, farbe, 2, cv2.LINE_AA)
			x += cv2.getTextSize(text, font, 0.8, 2)[0][0]

mittel = None
maxima_nm = []
beamer_fenster = None   # (Fenstername, Breite, Hoehe) solange ein HDMI-Geraet angeschlossen ist
letzte_hdmi_pruefung = 0.0
hdmi_kandidat = None  # letztes Pruefergebnis; geoeffnet wird erst bei zweimal gleichem Ergebnis
beamer_vollbild_ab = None  # Zeitpunkt, ab dem das Beamer-Fenster auf Vollbild geschaltet wird
bilder_gezaehlt, fps_start = 0, time.time()

def beamer_verwalten():
	"""HDMI pruefen: Beamer-Fenster oeffnen/schliessen (Fenstertitel steuert per labwc-Regel den Ausgang)."""
	global beamer_fenster, hdmi_kandidat, beamer_vollbild_ab
	ausgang = beamer.hdmi_ausgang()
	stabil = ausgang == hdmi_kandidat
	hdmi_kandidat = ausgang
	if not stabil:
		return  # Ausgang wird gerade eingerichtet (kanshi) -> naechste Pruefung abwarten
	if ausgang is None:
		if beamer_fenster is not None:
			cv2.destroyWindow(beamer_fenster[0])
			beamer_fenster = None
		return
	name = "Spektrometer Beamer " + ausgang[0]
	if beamer_fenster is not None and beamer_fenster[0] == name and beamer_fenster[3:] == (ausgang[1], ausgang[2]):
		return  # gleicher Ausgang, gleiche Aufloesung
	if beamer_fenster is not None:
		cv2.destroyWindow(beamer_fenster[0])
	w, h = beamer.zeichengroesse(ausgang[1], ausgang[2])
	# Die labwc-Fensterregel ("Spektrometer Beamer HDMI-A-x" -> MoveToOutput) legt das
	# Fenster auf den HDMI-Ausgang. Vollbild erst danach (s. Hauptschleife): Qt waehlt
	# fuer Vollbild den Bildschirm, auf dem das Fenster gerade liegt - direkt beim
	# Oeffnen waere das noch das 3,5"-Display.
	cv2.namedWindow(name, cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL)
	cv2.resizeWindow(name, w, h)
	beamer_vollbild_ab = time.time() + 1.0
	# (Name, Zeichenbreite, Zeichenhoehe, Ausgangsbreite, Ausgangshoehe)
	beamer_fenster = (name, w, h, ausgang[1], ausgang[2])
	print("Beamer-Ansicht auf", ausgang[0], ":", w, "x", h, "->", ausgang[1], "x", ausgang[2], flush=True)
kennwerte = None
letzte_cri = 0.0

def empfindlichkeit_laden():
	# optionale Korrektur der Kameraempfindlichkeit: CSV "Wellenlaenge,Faktor"
	# (wird spaeter mit einer Halogenlampe als Referenz erzeugt)
	try:
		d = np.loadtxt('empfindlichkeit.csv', delimiter=',', skiprows=1)
		return d[:, 0], d[:, 1]
	except Exception:
		return None

EMPFINDLICHKEIT = empfindlichkeit_laden()

def empfindlichkeit_faktor(wl):
	# nur gueltige Stuetzstellen (Faktor > 0); ausserhalb des gueltigen Bereichs 0.
	# (27.09. kurz Randwert gehalten -- das verstaerkte aber Streulicht jenseits der
	# Bildfeldkante; seit der Kantenerkennung im Assistenten ist der Bereich zuverlaessig.)
	w, f = EMPFINDLICHKEIT
	ok = f > 0
	if ok.sum() < 2:
		return np.ones_like(np.asarray(wl, dtype=float))
	return np.interp(wl, w[ok], f[ok], left=0, right=0)

def anzeige_faktor_und_maske():
	"""Fuer die Anzeige (nicht fuer Ra/CCT): innerhalb des kalibrierten Bereichs der
	Korrekturfaktor, ausserhalb der Randwert (Kurve laeuft weiter statt hart abzubrechen).
	Maske = True im kalibrierten Bereich; ausserhalb wird grau gezeichnet (28.09.)."""
	if EMPFINDLICHKEIT is None:
		return np.ones(len(wavelengthData)), np.ones(len(wavelengthData), dtype=bool)
	w, f = EMPFINDLICHKEIT
	ok = f > 0
	if ok.sum() < 2:
		return np.ones(len(wavelengthData)), np.ones(len(wavelengthData), dtype=bool)
	maske = empfindlichkeit_faktor(wavelengthData) > 0
	return np.interp(wavelengthData, w[ok], f[ok]), maske

ANZEIGE_FAKTOR, ANZEIGE_GUELTIG = anzeige_faktor_und_maske()
anzeige_skala = None

def korrigiert_fuer_anzeige(werte):
	"""Kurve fuer die Anzeige: Sockel abziehen, Empfindlichkeit korrigieren, auf 240 normieren."""
	global anzeige_skala
	werte = np.asarray(werte, dtype=float)
	if EMPFINDLICHKEIT is None:
		return np.clip(werte, 0, 255).astype(int)
	roh = np.clip(werte - np.percentile(werte, 5), 0, None)
	v = roh * ANZEIGE_FAKTOR
	if roh.max() < MIN_SIGNAL:
		# zu wenig Licht: nicht normieren, sonst wird Rauschen zur Scheinkurve aufgeblasen
		return np.clip(roh, 0, 255).astype(int)
	# Skala nur aus dem kalibrierten Bereich (grauer Rand bestimmt die Hoehe nicht)
	skala = 240.0 / max(v[ANZEIGE_GUELTIG].max() if ANZEIGE_GUELTIG.any() else v.max(), 1e-6)
	# Skala beruhigen, damit die Kurve bei Rauschen nicht pumpt
	anzeige_skala = skala if anzeige_skala is None else 0.8 * anzeige_skala + 0.2 * skala
	return np.clip(v * anzeige_skala, 0, 255).astype(int)

def lichtkennwerte(wl, werte):
	"""Ra, R9 und CCT aus dem gemessenen (relativen) Spektrum, CIE 13.3 via colour-science."""
	if not COLOUR_OK:
		return None
	wl = np.asarray(wl, dtype=float)
	v = np.asarray(werte, dtype=float)
	v = np.clip(v - np.percentile(v, 5), 0, None)  # Dunkel-/Streulichtsockel abziehen
	if v.max() < 8:
		return None  # zu wenig Licht fuer eine sinnvolle Rechnung
	if EMPFINDLICHKEIT is not None:
		v = v * empfindlichkeit_faktor(wl)
	reihenfolge = np.argsort(wl)
	wl, v = wl[reihenfolge], v[reihenfolge]
	raster = np.arange(380, 781, 5)
	sd = colour.SpectralDistribution(dict(zip(raster, np.interp(raster, wl, v, left=0, right=0))))
	try:
		spec = colour.colour_rendering_index(sd, additional_data=True)
		xy = colour.XYZ_to_xy(colour.sd_to_XYZ(sd))
		cct = float(colour.xy_to_CCT(xy, method='McCamy 1992'))
	except Exception as e:
		print("CRI-Berechnung fehlgeschlagen:", e)
		return None
	return {"ra": float(spec.Q_a), "r9": float(spec.Q_as[9].Q_a), "cct": cct, "bis_nm": float(wl.max())}

def kennwert_hinweise(k):
	"""Gruende, warum Ra/R9/CCT nur Schaetzwerte sind."""
	hinweise = []
	if k is None:
		return hinweise
	if "UNKAL" in calmsg1.upper():
		hinweise.append("unkalibriert")
	if k["bis_nm"] < 760:
		hinweise.append("nur bis %d nm" % k["bis_nm"])
	if EMPFINDLICHKEIT is None:
		hinweise.append("unkorrigiert")
	return hinweise

def kennwerte_zeichnen(graph, k):
	if k is None:
		return
	text = "Ra %d   R9 %d   %d K" % (round(k["ra"]), round(k["r9"]), round(k["cct"], -1))
	hinweise = kennwert_hinweise(k)
	x0, x1 = 470, 796
	hoehe = 44 if hinweise else 28
	cv2.rectangle(graph, (x0, 18), (x1, 18 + hoehe), (255, 255, 255), -1)
	cv2.rectangle(graph, (x0, 18), (x1, 18 + hoehe), (0, 0, 0), 1)
	cv2.putText(graph, text, (x0 + 8, 40), font, 0.65, (0, 0, 0), 2, cv2.LINE_AA)
	if hinweise:
		cv2.putText(graph, "Schaetzwert: " + ", ".join(hinweise), (x0 + 8, 56), font, 0.4, (0, 0, 180), 1, cv2.LINE_AA)

def snapshot(savedata):
	now = time.strftime("%Y%m%d--%H%M%S")
	timenow = time.strftime("%H:%M:%S")
	imdata1 = savedata[0]
	graphdata = savedata[1]
	if dispWaterfall == True:
		imdata2 = savedata[2]
		cv2.imwrite("waterfall-" + now + ".png",imdata2)
	cv2.imwrite("spectrum-" + now + ".png",imdata1)
	#print(graphdata[0]) #wavelengths
	#print(graphdata[1]) #intensities
	f = open("Spectrum-"+now+'.csv','w')
	f.write('Wavelength,Intensity\r\n')
	for x in zip(graphdata[0],graphdata[1]):
		f.write(str(x[0])+','+str(x[1])+'\r\n')
	f.close()
	message = "Last Save: "+timenow
	return(message)


while True:
	# Capture frame-by-frame
	frame, bilddaten = kamera.bild_mit_daten(picam2)
	y=int((frameHeight/2)-40) #origin of the vertical crop
	#y=200 	#origin of the vert crop
	x=0   	#origin of the horiz crop
	h=80 	#height of the crop
	w=frameWidth 	#width of the crop
	cropped = frame[y:y+h, x:x+w]
	# Messwert = Mittel der drei Farbkanaele (Summe/3) statt Augen-Gewichtung (Blau
	# nur 11 %) oder Maximum (bricht an den Kanaluebergaengen ein)
	bwimage = (cropped.astype(np.uint16).sum(axis=2) // 3).astype(np.uint8)
	rows,cols = bwimage.shape
	halfway =int(rows/2)
	#show our line on the original image
	#now a 3px wide region
	cv2.line(cropped,(0,halfway-2),(frameWidth,halfway-2),(255,255,255),1)
	cv2.line(cropped,(0,halfway+2),(frameWidth,halfway+2),(255,255,255),1)

	messages = buttonleiste(saveMsg)

	#blank image for Graph
	graph = np.zeros([320,frameWidth,3],dtype=np.uint8)
	graph.fill(255) #fill white

	#Display a graticule calibrated with cal data
	textoffset = 12
	#vertial lines every whole 10nm
	for position in tens:
		cv2.line(graph,(position,15),(position,320),(200,200,200),1)

	#vertical lines every whole 50nm
	for positiondata in fifties:
		cv2.line(graph,(positiondata[0],15),(positiondata[0],320),(0,0,0),1)
		cv2.putText(graph,str(positiondata[1])+'nm',(positiondata[0]-textoffset,12),font,0.4,(0,0,0),1, cv2.LINE_AA)

	#horizontal lines
	for i in range (320):
		if i>=64:
			if i%64==0: #suppress the first line then draw the rest...
				cv2.line(graph,(0,i),(frameWidth,i),(100,100,100),1)
	
	#Now process the intensity data and display it
	#intensity = []
	# Messprofil linear aus den Sensor-Rohdaten (kamera.zeilenprofil), nicht aus dem
	# ISP-Bild (nichtlinear bei schwachen Signalen, 28.09.)
	profil = kamera.zeilenprofil(frame)
	for i in range(cols):
		data = float(profil[i])
		if holdpeaks == True:
			if data > intensity[i]:
				intensity[i] = data
		else:
			intensity[i] = data

	# Belichtung langsam nachfuehren, damit nichts uebersteuert. Eine Aenderung wirkt
	# erst nach einigen Bildern -> erst nachregeln, wenn die letzte Einstellung greift.
	# (Die Anzeige ist normiert, Ra/CCT haengen nur von der Kurvenform ab.)
	aussteuerung = int(kamera.kanalmaximum(frame).max())  # hellster Kanal (Rohdaten: 255 = Sensor voll)
	if belichtung_auto and kamera.belichtung_wirksam(bilddaten, belichtung_soll):
		spitze = aussteuerung
		neu = belichtung_soll
		if spitze >= 250:
			neu = belichtung_soll * 0.5
		elif spitze < 100:
			neu = belichtung_soll * 1.6
		neu = int(min(max(neu, 100), 1000000))  # bis 1 s
		if neu != belichtung_soll:
			belichtung_soll = neu
			picam2.set_controls({"ExposureTime": belichtung_soll})

	if dispWaterfall == True:
		#waterfall....
		#data is smoothed at this point!!!!!!
		#create an empty array for the data
		wdata = np.zeros([1,frameWidth,3],dtype=np.uint8)
		index=0
		for i in intensity:
			rgb = wavelength_to_rgb(round(wavelengthData[index]))#derive the color from the wavelenthData array
			luminosity = intensity[index]/255
			b = int(round(rgb[0]*luminosity))
			g = int(round(rgb[1]*luminosity))
			r = int(round(rgb[2]*luminosity))
			#print(b,g,r)
			#wdata[0,index]=(r,g,b) #fix me!!! how do we deal with this data??
			wdata[0,index]=(r,g,b)
			index+=1
		#bright and contrast of final image
		contrast = 2.5
		brightness =10
		wdata = cv2.addWeighted( wdata, contrast, wdata, 0, brightness)
		waterfall = np.insert(waterfall, 0, wdata, axis=0) #insert line to beginning of array
		waterfall = waterfall[:-1].copy() #remove last element from array

		hsv = cv2.cvtColor(waterfall, cv2.COLOR_BGR2HSV)


	#Draw the intensity data :-)
	#first filter if not holding peaks!
	
	if holdpeaks == False:
		intensity = np.array(savitzky_golay(np.asarray(intensity, dtype=float),GLAETTUNG_FENSTER,GLAETTUNG_ORDNUNG), dtype=float)
		if ZEITMITTEL > 0 and mittel is not None and len(mittel) == len(intensity):
			mittel = ZEITMITTEL*mittel + (1-ZEITMITTEL)*intensity
		else:
			mittel = intensity
		intensity = np.clip(mittel, 0, 255).astype(int)
		holdmsg = "Holdpeaks OFF" 
	else:
		holdmsg = "Holdpeaks ON"
	anzeige = korrigiert_fuer_anzeige(intensity)  # Rohdaten bleiben in intensity (fuer CRI)
		
	
	#now draw the intensity data....
	index=0
	for i in anzeige:
		rgb = wavelength_to_rgb(round(wavelengthData[index]))#derive the color from the wvalenthData array
		if not ANZEIGE_GUELTIG[index]:
			rgb = (175, 175, 175)  # ausserhalb des kalibrierten Bereichs: grau
		r = rgb[0]
		g = rgb[1]
		b = rgb[2]
		#or some reason origin is top left.
		cv2.line(graph, (index,320), (index,320-i), (b,g,r), 1)
		cv2.line(graph, (index,319-i), (index,320-i), (0,0,0), 1,cv2.LINE_AA)
		index+=1


	#find peaks and label them
	textoffset = 12
	thresh = int(thresh) #make sure the data is int.
	indexes = peakIndexes(anzeige, thres=thresh/max(max(anzeige),1), min_dist=mindist)
	# nur die staerksten Maxima beschriften
	indexes = sorted(indexes, key=lambda k: anzeige[k], reverse=True)[:ANZAHL_MAXIMA]
	maxima_nm = sorted(round(wavelengthData[k], 1) for k in indexes)
	for i in indexes:
		height = anzeige[i]
		height = 310-height
		wavelength = round(wavelengthData[i],1)
		cv2.rectangle(graph,((i-textoffset)-2,height),((i-textoffset)+60,height-15),(0,255,255),-1)
		cv2.rectangle(graph,((i-textoffset)-2,height),((i-textoffset)+60,height-15),(0,0,0),1)
		cv2.putText(graph,str(wavelength)+'nm',(i-textoffset,height-3),font,0.4,(0,0,0),1, cv2.LINE_AA)
		#flagpoles
		cv2.line(graph,(i,height),(i,height+10),(0,0,0),1)


	# Farbwiedergabe (Ra, R9) und Farbtemperatur, einmal pro Sekunde neu berechnet
	if time.time() - letzte_cri > 1.0:
		kennwerte = lichtkennwerte(wavelengthData, intensity)
		letzte_cri = time.time()
	kennwerte_zeichnen(graph, kennwerte)

	if measure == True:
		#show the cursor!
		cv2.line(graph,(cursorX,cursorY-140),(cursorX,cursorY-180),(0,0,0),1)
		cv2.line(graph,(cursorX-20,cursorY-160),(cursorX+20,cursorY-160),(0,0,0),1)
		cv2.putText(graph,str(round(wavelengthData[cursorX],2))+'nm',(cursorX+5,cursorY-165),font,0.4,(0,0,0),1, cv2.LINE_AA)

	if recPixels == True:
		#display the points
		cv2.line(graph,(cursorX,cursorY-140),(cursorX,cursorY-180),(0,0,0),1)
		cv2.line(graph,(cursorX-20,cursorY-160),(cursorX+20,cursorY-160),(0,0,0),1)
		cv2.putText(graph,str(cursorX)+'px',(cursorX+5,cursorY-165),font,0.4,(0,0,0),1, cv2.LINE_AA)
	else:
		#also make sure the click array stays empty
		clickArray = []

	if clickArray:
		for data in clickArray:
			mouseX=data[0]
			mouseY=data[1]
			cv2.circle(graph,(mouseX,mouseY),5,(0,0,0),-1)
			#we can display text :-) so we can work out wavelength from x-pos and display it ultimately
			cv2.putText(graph,str(mouseX),(mouseX+5,mouseY),cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,0,0))
	



	#stack the images and display the spectrum	
	spectrum_vertical = np.vstack((messages,cropped, graph))
	#dividing lines...
	cv2.line(spectrum_vertical,(0,80),(frameWidth,80),(255,255,255),1)
	cv2.line(spectrum_vertical,(0,160),(frameWidth,160),(255,255,255),1)
	status_einblenden(spectrum_vertical, saveMsg)
	cv2.imshow(title1,spectrum_vertical)

	# Beamer/Monitor an HDMI: eigene, hochaufgeloeste Ansicht
	if time.time() - letzte_hdmi_pruefung > 2.0:
		beamer_verwalten()
		letzte_hdmi_pruefung = time.time()
	if beamer_fenster is not None:
		kurvenart = "korrigiert, normiert" if EMPFINDLICHKEIT is not None else "unkorrigiert"
		bb = beamer.zeichnen(beamer_fenster[1], beamer_fenster[2], wavelengthData, anzeige, cropped,
		                     indexes, kennwerte, kennwert_hinweise(kennwerte), calmsg1,
		                     saveMsg, kurvenart, wavelength_to_rgb, gueltig=ANZEIGE_GUELTIG)
		if (beamer_fenster[3], beamer_fenster[4]) != (beamer_fenster[1], beamer_fenster[2]):
			# Qt skaliert im Vollbild nicht hoch -> selbst auf Ausgangsaufloesung bringen
			bb = cv2.resize(bb, (beamer_fenster[3], beamer_fenster[4]), interpolation=cv2.INTER_LINEAR)
		cv2.imshow(beamer_fenster[0], bb)
		if beamer_vollbild_ab is not None and time.time() >= beamer_vollbild_ab:
			cv2.setWindowProperty(beamer_fenster[0], cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
			beamer_vollbild_ab = None
	bilder_gezaehlt += 1
	if time.time() - fps_start > 10:
		print("Bildrate %.1f fps" % (bilder_gezaehlt / (time.time() - fps_start)), flush=True)
		bilder_gezaehlt, fps_start = 0, time.time()

	if dispWaterfall == True:
		#stack the images and display the waterfall	
		waterfall_vertical = np.vstack((messages,cropped, waterfall))
		#dividing lines...
		cv2.line(waterfall_vertical,(0,80),(frameWidth,80),(255,255,255),1)
		cv2.line(waterfall_vertical,(0,160),(frameWidth,160),(255,255,255),1)
		#Draw this stuff over the top of the image!
		#Display a graticule calibrated with cal data
		textoffset = 12

		#vertical lines every whole 50nm
		for positiondata in fifties:
			for i in range(162,480):
				if i%20 == 0:
					cv2.line(waterfall_vertical,(positiondata[0],i),(positiondata[0],i+1),(0,0,0),2)
					cv2.line(waterfall_vertical,(positiondata[0],i),(positiondata[0],i+1),(255,255,255),1)
			cv2.putText(waterfall_vertical,str(positiondata[1])+'nm',(positiondata[0]-textoffset,475),font,0.4,(0,0,0),2, cv2.LINE_AA)
			cv2.putText(waterfall_vertical,str(positiondata[1])+'nm',(positiondata[0]-textoffset,475),font,0.4,(255,255,255),1, cv2.LINE_AA)

		cv2.putText(waterfall_vertical,calmsg1,(490,15),font,0.4,(0,255,255),1, cv2.LINE_AA)
		cv2.putText(waterfall_vertical,calmsg3,(490,33),font,0.4,(0,255,255),1, cv2.LINE_AA)
		cv2.putText(waterfall_vertical,saveMsg,(490,51),font,0.4,(0,255,255),1, cv2.LINE_AA)
		cv2.putText(waterfall_vertical,"Gain: "+str(picamGain),(490,69),font,0.4,(0,255,255),1, cv2.LINE_AA)
		
		cv2.putText(waterfall_vertical,holdmsg,(640,15),font,0.4,(0,255,255),1, cv2.LINE_AA)

		cv2.imshow(title2,waterfall_vertical)


	keyPress = cv2.waitKey(1)
	if aktion == "speichern":
		saveMsg = auf_usb_speichern(graph, maxima_nm)
		print(saveMsg)
	elif aktion == "beenden":
		break
	elif aktion == "auto":
		belichtung_auto = not belichtung_auto
	elif aktion in ("heller", "dunkler"):
		# von Hand: naechste Stufe; Tippen im Auto-Modus schaltet auf manuell
		belichtung_auto = False
		i = min(range(len(STUFEN_US)), key=lambda k: abs(STUFEN_US[k] - belichtung_soll))
		i = min(i + 1, len(STUFEN_US) - 1) if aktion == "heller" else max(i - 1, 0)
		belichtung_soll = STUFEN_US[i]
		picam2.set_controls({"ExposureTime": belichtung_soll})
	elif aktion == "kalibrieren":
		# Kamera freigeben, Assistent starten, danach neu starten (laedt neue Kalibrierung)
		picam2.stop()
		picam2.close()
		cv2.destroyAllWindows()
		for _ in range(5):
			cv2.waitKey(10)
		ergebnis = subprocess.run([sys.executable, "kalibrierung.py"])
		print("Kalibrier-Assistent beendet mit Code", ergebnis.returncode, flush=True)
		os.execv(sys.executable, [sys.executable] + sys.argv)
	aktion = None
	if keyPress == ord('q'):
		break
	elif keyPress == ord('h'):
		if holdpeaks == False:
			holdpeaks = True
		elif holdpeaks == True:
			holdpeaks = False
	elif keyPress == ord("s"):
		#package up the data!
		graphdata = []
		graphdata.append(wavelengthData)
		graphdata.append(anzeige)
		if dispWaterfall == True:
			savedata = []
			savedata.append(spectrum_vertical)
			savedata.append(graphdata)
			savedata.append(waterfall_vertical)
		else:
			savedata = []
			savedata.append(spectrum_vertical)
			savedata.append(graphdata)
		saveMsg = snapshot(savedata)
	elif keyPress == ord("c"):
		calcomplete = writecal(clickArray)
		if calcomplete:
			#overwrite wavelength data
			#Go grab the computed calibration data
			caldata = readcal(frameWidth)
			wavelengthData = caldata[0]
			ANZEIGE_FAKTOR, ANZEIGE_GUELTIG = anzeige_faktor_und_maske()
			calmsg1 = caldata[1]
			calmsg2 = caldata[2]
			calmsg3 = caldata[3]
			#overwrite graticule data
			graticuleData = generateGraticule(wavelengthData)
			tens = (graticuleData[0])
			fifties = (graticuleData[1])
	elif keyPress == ord("x"):
		clickArray = []
	elif keyPress == ord("m"):
		recPixels = False #turn off recpixels!
		if measure == False:
			measure = True
		elif measure == True:
			measure = False
	elif keyPress == ord("p"):
		measure = False #turn off measure!
		if recPixels == False:
			recPixels = True
		elif recPixels == True:
			recPixels = False
	elif keyPress == ord("o"):#sav up
			savpoly+=1
			if savpoly >=15:
				savpoly=15
	elif keyPress == ord("l"):#sav down
			savpoly-=1
			if savpoly <=0:
				savpoly=0
	elif keyPress == ord("i"):#Peak width up
			mindist+=1
			if mindist >=100:
				mindist=100
	elif keyPress == ord("k"):#Peak Width down
			mindist-=1
			if mindist <=0:
				mindist=0
	elif keyPress == ord("u"):#label thresh up
			thresh+=1
			if thresh >=100:
				thresh=100
	elif keyPress == ord("j"):#label thresh down
			thresh-=1
			if thresh <=0:
				thresh=0

	elif keyPress == ord("t"):#Gain up!
			picamGain += 1
			if picamGain >=50:
				picamGain = 50.0
			picam2.set_controls({"AnalogueGain": picamGain})
			print("Camera Gain: "+str(picamGain))
	elif keyPress == ord("g"):#Gain down
			picamGain -= 1
			if picamGain <=0:
				picamGain = 0.0
			picam2.set_controls({"AnalogueGain": picamGain})
			print("Camera Gain: "+str(picamGain))								
				


 
#Everything done
cv2.destroyAllWindows()


