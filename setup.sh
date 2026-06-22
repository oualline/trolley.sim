sudo apt install vim-gtk3
sudo apt-get install default-jre libreoffice-java-common
sudo apt install python3-pip
sudo apt install python3-pynput
sudo apt install python3-opencv
sudo apt install python3-mpv

# For qt6
sudo apt install pyqt6-dev-tools python3-pyqt6
sudo apt install designer-qt6
sudo apt install qmake6

echo "/usr/lib/qt6/bin" | sudo tee /usr/lib/x86_64-linux-gnu/qtchooser/qt6.conf
echo "/usr/lib/x86_64-linux-gnu" | sudo tee -a /usr/lib/x86_64-linux-gnu/qtchooser/qt6.conf

# For mpv video playback
sudo apt install libmpv-dev

# Python packages
sudo pip install \
    playsound3 \
    pyinstaller \
    --break-system-packages
