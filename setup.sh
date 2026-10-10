#!/bin/bash
# Setup script for trolley.sim development on Linux (Ubuntu/Debian).

# Editor and source control
sudo apt install vim-gtk3 git

# LibreOffice Writer: the Makefile uses "libreoffice --headless" to turn
# help.odt and quick.odt into PDFs
sudo apt install libreoffice-writer
sudo apt-get install default-jre libreoffice-java-common

# Python and the modules the program imports
sudo apt install python3-pip
sudo apt install python3-pynput          # main.py
sudo apt install python3-mpv             # video.py (pulls in libmpv2)

# Qt6 / PyQt6
sudo apt install python3-pyqt6           # QtCore, QtGui, QtWidgets, QtOpenGLWidgets
sudo apt install python3-pyqt6.qtpdf     # QtPdf, QtPdfWidgets (help_viewer.py)
sudo apt install python3-pyqt6.qtsvg     # SVG icons used in the .ui files
sudo apt install pyqt6-dev-tools         # pyuic6, used by the Makefile
sudo apt install designer-qt6            # Qt Designer, for editing the .ui files

# Only needed for the video_to_frames.py utility, not for the simulator
sudo apt install python3-opencv

# Python packages not packaged by apt
sudo pip install \
    playsound3 \
    pyinstaller \
    --break-system-packages

# Make the "designer" command run the Qt6 version
sudo apt install qtchooser
echo "/usr/lib/qt6/bin" | sudo tee /usr/lib/x86_64-linux-gnu/qtchooser/qt6.conf
echo "/usr/lib/x86_64-linux-gnu" | sudo tee -a /usr/lib/x86_64-linux-gnu/qtchooser/qt6.conf

DIR=/usr/lib/x86_64-linux-gnu/qtchooser/
sudo ln -f $DIR/qt6.conf $DIR/default.conf
