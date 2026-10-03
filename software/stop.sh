#!/bin/sh
pkill -f "venv/bin/python3 spektrometer.py"
pkill -f "^python3 (PySpectrometer2-Picam2|spektrometer|linienmessung)"
exit 0
