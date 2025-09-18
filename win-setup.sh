cat >>.bashrc
P=/cygdrive/c/Users/User/AppData/Local/Programs/Python/Python313
PI=/cygdrive/c/Users/User/AppData/Local/Programs/Python/Python313/Scripts
export PATH=$PATH:$P:$PI

EOF

. .bashrc
apt install gcc-core
apt install libgirepository1.0-devel
apt install cmake gcc-g++
apt install python3-cairo
apt install libcairo-devel

pip3 install python-vlc
pip3 install PyQt5
pip3 install PyGObject

pip install pyinstaller
