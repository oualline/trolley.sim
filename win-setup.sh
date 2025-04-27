cat >>.bashrc
P=/cygdrive/c/Users/User/AppData/Local/Programs/Python/Python313
PI=/cygdrive/c/Users/User/AppData/Local/Programs/Python/Python313/Scripts
export PATH=$PATH:$P:$PI

EOF

. .bashrc
pip3 install python-vlc
pip3 install PyQt5

pip install pyinstaller
