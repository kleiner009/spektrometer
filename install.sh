#!/bin/bash
# Installation "Spektrometer fuer Leuchtmittel" auf Raspberry Pi 5 (Raspberry Pi OS Trixie/Bookworm, Desktop)
# Aufruf im Repository-Ordner:  ./install.sh
# Installiert nach ~/Spektrometer. Bestehende Konfigurationsdateien werden nicht ueberschrieben.
set -e

ZIEL="$HOME/Spektrometer"
QUELLE="$(cd "$(dirname "$0")" && pwd)"

frage() {  # frage "Text" -> 0 bei j/J
	read -r -p "$1 [j/N] " a
	[ "$a" = "j" ] || [ "$a" = "J" ]
}

echo "== 1/6 Pakete installieren (sudo) =="
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv python3-numpy python3-pil python3-venv \
	fonts-dejavu-core wlr-randr kanshi

echo "== 2/6 Programm nach $ZIEL kopieren =="
mkdir -p "$ZIEL"
cp "$QUELLE"/software/*.py "$QUELLE"/software/*.sh "$ZIEL"/
chmod +x "$ZIEL"/*.sh

echo "== 3/6 Python-Umgebung mit colour-science (Ra, R9, Farbtemperatur) =="
if [ ! -d "$ZIEL/venv" ]; then
	python3 -m venv --system-site-packages "$ZIEL/venv"   # picamera2/cv2 kommen aus dem System
fi
"$ZIEL/venv/bin/pip" install --upgrade colour-science

echo "== 4/6 Hardware in /boot/firmware/config.txt =="
CFG=/boot/firmware/config.txt
if frage "Arducam OV9281 Mono an CAM0 eintragen (dtoverlay=ov9281,cam0,arducam)?"; then
	grep -q "dtoverlay=ov9281" "$CFG" || { sudo cp "$CFG" "$CFG.vor-spektrometer"; \
		printf '\n# Spektrometer: OV9281 Mono an CAM0\ndtoverlay=ov9281,cam0,arducam\n' | sudo tee -a "$CFG" >/dev/null; }
fi
if frage "3,5\"-SPI-Display (ILI9486/XPT2046, z. B. AZ-Delivery) eintragen?"; then
	grep -q "dtoverlay=piscreen" "$CFG" || { sudo cp "$CFG" "$CFG.vor-display"; \
		printf '\n# Spektrometer: 3,5"-SPI-Display\ndtparam=spi=on\ndtoverlay=piscreen,drm,speed=16000000,invy\n' | sudo tee -a "$CFG" >/dev/null; }
fi

echo "== 5/6 Desktop: Autostart, Fensterregeln, Bildschirmprofile, Verknuepfung =="
mkdir -p "$HOME/.config/labwc" "$HOME/.config/kanshi" "$HOME/Desktop"
AUTO="$HOME/.config/labwc/autostart"
grep -q "Spektrometer/start.sh" "$AUTO" 2>/dev/null || \
	echo "sh -c \"sleep 5; $ZIEL/start.sh\" &" >> "$AUTO"
if [ -f "$HOME/.config/labwc/rc.xml" ]; then
	cp "$QUELLE/system/labwc_rc.xml" "$HOME/.config/labwc/rc.xml.spektrometer"
	echo "  HINWEIS: rc.xml existiert schon -> Vorlage liegt als rc.xml.spektrometer daneben."
	echo "           Die <windowRules> von Hand uebernehmen (Touch-Matrix gilt nur fuer das Original-Display)."
else
	cp "$QUELLE/system/labwc_rc.xml" "$HOME/.config/labwc/rc.xml"
fi
[ -f "$HOME/.config/kanshi/config" ] || cp "$QUELLE/system/kanshi_config" "$HOME/.config/kanshi/config"
cat > "$HOME/Desktop/Spektrometer.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Spektrometer
Comment=Spektrum von Leuchtmitteln messen (Ra, R9, Farbtemperatur)
Exec=$ZIEL/start.sh
Icon=applications-science
Terminal=false
Categories=Education;Science;
EOF
chmod +x "$HOME/Desktop/Spektrometer.desktop"

echo "== 6/6 Fertig =="
echo "Jetzt neu starten (sudo reboot). Danach startet das Spektrometer automatisch."
echo "Erster Schritt: Taste 'Kalibrieren' und den Assistenten komplett durchlaufen,"
echo "anschliessend im Ordner $ZIEL:  venv/bin/python3 zuschnitt.py   (Achse auf 360-800 nm)."
