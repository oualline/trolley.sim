REM After installation of python
REM Run as admin
setx /m PATH "%PATH%;C:\Program Files (x86)\GnuWin32\bin"
setx /m PATH "%PATH%;C:\Users\user\AppData\Local\Python\pythoncore-3.14-64\Scripts"
pip install PyQt6
pip install playsound3
pip install pyinstaller
pip install pyinput
pip install Pillow
pip install opencv-python
winget install GnuWin32.Make
echo "Add C:\Program Files (x86)\GnuWin32\bin to your path (if not there)"
