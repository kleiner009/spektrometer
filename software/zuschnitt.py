import json, os, shutil, time
import numpy as np
from specFunctions import zuordnung_berechnen
VON, BIS = 360.0, 800.0
e = json.load(open('kamera_einstellungen.json'))
z = open('caldata.txt').read().split('\n')
px = [float(v) for v in z[0].split(',')]; nm = [float(v) for v in z[1].split(',')]
wl, art = zuordnung_berechnen(px, nm, 800)
x = np.arange(800.0)
pa, pb = float(np.interp(VON, wl, x)), float(np.interp(BIS, wl, x))
cx, cy, cw, ch = e['crop']
s = cw / 800.0                                  # Sensorpixel je Bildspalte
nx0 = cx + pa * s; nw = (pb - pa) * s
nw = int(round(nw / 4)) * 4; nh = nw * 3 // 4
mitte_y = cy + ch / 2
neu = [int(round(nx0)) & ~1, int(round(mitte_y - nh / 2)) & ~1, nw, nh]
# Kalibrierpunkte in neue Spalten umrechnen (affin -> gleiche Kurve)
skal = 800.0 / (nw / s)
versatz = (neu[0] - cx) / s
npx = [(p - versatz) * skal for p in px]
wl2, art2 = zuordnung_berechnen(npx, nm, 800)
print('alt', e['crop'], 'Achse %.1f-%.1f' % (wl[0], wl[-1]), art)
print('neu', neu, 'Achse %.1f-%.1f' % (wl2[0], wl2[-1]), art2, 'Punkte', [round(p, 2) for p in npx])
# Gegenprobe: gleiche Wellenlaenge je Sensorpixel
for sp in (cx + 200 * s, cx + 400 * s):
    a = np.interp((sp - cx) / s, x, wl); b = np.interp((sp - neu[0]) / (nw / 800.0), x, wl2)
    print('Sensorpixel %.0f: alt %.2f nm, neu %.2f nm' % (sp, a, b))
stempel = time.strftime('%Y%m%d-%H%M%S')
ziel = os.path.join('alt', stempel + '-zuschnitt'); os.makedirs(ziel)
for d in ('kamera_einstellungen.json', 'caldata.txt'):
    shutil.copy2(d, ziel)
e['crop'] = neu; e['stand'] = stempel + ' (Zuschnitt %d-%d nm)' % (VON, BIS)
json.dump(e, open('kamera_einstellungen.json', 'w'), indent=2)
open('caldata.txt', 'w').write(','.join('%.2f' % p for p in npx) + '\n' + ','.join('%.1f' % v for v in nm) + '\n')
print('gesichert in', ziel)
