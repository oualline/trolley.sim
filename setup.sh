sudo apt install vim-gtk3 git
sudo apt-get install default-jre libreoffice-java-common
sudo apt install python3-pip
sudo apt install python3-pynput
sudo apt install python3-opencv
sudo apt install python3-mpv

# For qt6
sudo apt install pyqt6-dev-tools python3-pyqt6
sudo apt install designer-qt6
sudo apt install qmake6


# For mpv video playback
sudo apt install libmpv-dev

# Python packages
sudo pip install \
    playsound3 \
    pyinstaller \
    --break-system-packages


sudp apt install qtchooser
sudo apt install python3-pyqt6.qtsvg
echo "/usr/lib/qt6/bin" | sudo tee /usr/lib/x86_64-linux-gnu/qtchooser/qt6.conf
echo "/usr/lib/x86_64-linux-gnu" | sudo tee -a /usr/lib/x86_64-linux-gnu/qtchooser/qt6.conf

DIR=/usr/lib/x86_64-linux-gnu/qtchooser/
#sudo sed -e 's/5/6/g' $DIR/qt5.conf >$DIR/qt6.conf
sudo ln $DIR/qt6.conf $DIR/default.conf
