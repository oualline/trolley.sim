@echo off
REM Setup script for trolley.sim development on Windows.
REM See win-setup.txt.  Install Python 3.x first, then run this from a
REM command window opened with "Run as administrator".

REM ------------------------------------------------------------------
REM Must be elevated: the PATH change below is machine-wide.
REM ------------------------------------------------------------------
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click "Command Prompt", choose "Run as administrator",
    echo then run win-setup.bat again.
    pause
    exit /b 1
)

REM ------------------------------------------------------------------
REM GNU make
REM ------------------------------------------------------------------
winget install --accept-source-agreements --accept-package-agreements GnuWin32.Make
REM (A non-zero exit here usually just means it is already installed.)

REM ------------------------------------------------------------------
REM Add GnuWin32 make and mpv to the system PATH.
REM
REM Do NOT use  setx /m PATH "%%PATH%%;..."  for this.  %%PATH%% is this
REM window's PATH (system + user entries merged), so setx copies the user
REM entries into the system PATH, truncates the result at 1024 characters,
REM and -- because %%PATH%% is not updated by setx -- a second setx line
REM overwrites the first one.
REM
REM Instead, read the system PATH straight from the registry (unexpanded, so
REM entries like %%SystemRoot%% survive), append each directory only if it
REM is missing, and write it back as REG_EXPAND_SZ.  The final
REM SetEnvironmentVariable call on a dummy name is only there to broadcast
REM the change, so newly opened windows see the new PATH.
REM ------------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $key = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SYSTEM\CurrentControlSet\Control\Session Manager\Environment', $true); $path = $key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames); foreach ($dir in @('C:\Program Files (x86)\GnuWin32\bin', 'C:\mpv')) { if (($path -split ';') -notcontains $dir) { $path = $path.TrimEnd(';') + ';' + $dir; Write-Host ('Added to system PATH: ' + $dir) } else { Write-Host ('Already in system PATH: ' + $dir) } }; $key.SetValue('Path', $path, [Microsoft.Win32.RegistryValueKind]::ExpandString); $key.Close(); [Environment]::SetEnvironmentVariable('TROLLEY_SETUP_BROADCAST', $null, 'User')"
if errorlevel 1 (
    echo ERROR: Could not update the system PATH.
    pause
    exit /b 1
)

REM Also make the new directories usable in this window.
set "PATH=%PATH%;C:\Program Files (x86)\GnuWin32\bin;C:\mpv"

REM ------------------------------------------------------------------
REM Python packages.  "python -m pip" works even when pip's Scripts
REM directory is not on PATH (common with the Microsoft Store Python).
REM ------------------------------------------------------------------
python -m pip install PyQt6 playsound3 pyinstaller pynput python-mpv
if errorlevel 1 (
    echo ERROR: pip install failed.  Is Python installed and on PATH?
    pause
    exit /b 1
)

REM ------------------------------------------------------------------
REM libmpv
REM ------------------------------------------------------------------
if not exist "C:\mpv\libmpv-2.dll" (
    echo.
    echo NOTE: C:\mpv\libmpv-2.dll was not found.
    echo    python-mpv and the Windows build need it.  See install-libmvp.md:
    echo    download the mpv Windows build from
    echo    https://sourceforge.net/projects/mpv-player-windows/
    echo    and copy libmpv-2.dll into C:\mpv
)

echo.
echo Setup complete.  Close this window and open a new one so the new
echo PATH takes effect everywhere.
pause
