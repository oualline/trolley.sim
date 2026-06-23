REM Setup script for trolley.sim on Windows
REM Run as Administrator after installing Python 3.x

REM Add GnuWin32 and Python Scripts to system PATH
winget install GnuWin32.Make
setx /m PATH "%PATH%;C:\Program Files (x86)\GnuWin32\bin"
setx /m PATH "%PATH%;C:\mpv"

REM Install required Python packages
pip install PyQt6
pip install playsound3
pip install pyinstaller
pip install pynput
pip install python-mpv

REM python-mpv requires libmpv-2.dll — install mpv from https://mpv.io/installation/
REM and copy libmpv-2.dll to your Python Scripts folder or somewhere on PATH.
REM Recommended: use the mpv Windows build from https://sourceforge.net/projects/mpv-player-windows/

echo python-mpv requires libmpv-2.dll — install mpv from https://mpv.io/installation/
echo    and copy libmpv-2.dll to your Python Scripts folder or somewhere on PATH.
echo    Recommended: use the mpv Windows build from https://sourceforge.net/projects/mpv-player-windows/
