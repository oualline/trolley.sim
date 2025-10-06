#!/bin/bash

echo "=========================================="
echo "Trolley Simulator Dependency Installation"
echo "=========================================="
echo ""

# Update MSYS2
echo "Step 1: Updating MSYS2..."
pacman -Syu --noconfirm

# Install all MSYS2 packages
echo ""
echo "Step 2: Installing MSYS2 packages..."
# Use --noconfirm to avoid confirmation
pacman -S --needed mingw-w64-x86_64-python 
pacman -S --needed mingw-w64-x86_64-python-pip 
pacman -S --needed mingw-w64-x86_64-gcc 
pacman -S --needed mingw-w64-x86_64-pkg-config 
pacman -S --needed mingw-w64-x86_64-python-pyqt5 
pacman -S --needed mingw-w64-x86_64-gstreamer 
pacman -S --needed mingw-w64-x86_64-gst-plugins-base 
pacman -S --needed mingw-w64-x86_64-gst-plugins-good 
pacman -S --needed mingw-w64-x86_64-gst-plugins-bad 
pacman -S --needed mingw-w64-x86_64-gst-plugins-ugly 
pacman -S --needed mingw-w64-x86_64-python-gobject 
pacman -S --needed mingw-w64-x86_64-vlc
pacman -S --needed mingw-w64-x86_64-json-glib
pacman -S --needed make
pacman -S --needed vim

# Install Python packages
echo ""
echo "Step 3: Installing Python packages via pip..."
pip install python-vlc 
pip install pyinstaller

# Verify installations
echo ""
echo "Step 4: Verifying installations..."
echo ""

echo -n "Python version: "
python --version

echo -n "PyQt5: "
python -c "from PyQt5 import QtWidgets; print('OK')" 2>/dev/null && echo "OK" || echo "FAILED"

echo -n "VLC: "
python -c "import vlc; print('OK')" 2>/dev/null && echo "OK" || echo "FAILED"

echo -n "GStreamer: "
gst-launch-1.0 --version | head -n 1

echo -n "PyInstaller: "
pyinstaller --version

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
