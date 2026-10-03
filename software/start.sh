#!/bin/sh
# Spektrometer im Vollbild starten (Desktop-Verknuepfung und Autostart)
cd "$(dirname "$(readlink -f "$0")")"
# nur eine Instanz: die Kamera kann nur von einem Programm genutzt werden
if pgrep -f "venv/bin/python3 spektrometer.py" > /dev/null; then
	exit 0
fi
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}
exec venv/bin/python3 spektrometer.py --fullscreen >> spektrometer.log 2>&1
