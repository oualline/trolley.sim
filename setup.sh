sudo apt install mpg321
#sudo apt install pyqt5-dev-tools
#sudo apt install python3-pyqt5
#sudo apt install python3-vlc
#sudo apt install qttools5-dev-tools
sudo apt install vim-gtk3
sudo apt-get install default-jre libreoffice-java-common
sudo apt install python3-pip
sudo pip install playsound3 --break-system-packages
sudo apt install python3-pynput
sudo apt install python3-opencv

# For gstreamer which has proven to complex
#sudo apt install python-gobject-devel

# For qt6
sudo apt install pyqt6-dev-tools python3-pyqt6
sudo apt install designer-qt6
sudo apt install qmake6

echo "/usr/lib/qt6/bin" | sudo tee /usr/lib/x86_64-linux-gnu/qtchooser/qt6.conf
echo "/usr/lib/x86_64-linux-gnu" | sudo tee -a /usr/lib/x86_64-linux-gnu/qtchooser/qt6.conf
