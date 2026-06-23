# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['brake_ui.py', 'controller.py', 'main.py', 'mode_window.py', 'sim_ui4.py', 'sound.py', 'state.py', 'video.py', 'video_player.py'],
    pathex=[],
    binaries=[
        ('image/*.png', 'image'),
        ('image/*.svg', 'image'),
        # libmpv-2.dll must be on PATH or placed next to the executable.
        # Obtain it from https://sourceforge.net/projects/mpv-player-windows/
        # Uncomment the line below once you have the DLL:
        ('C:\\mpv\\libmpv-2.dll', '.'),
    ],
    datas=[
        ('image/splash.png', '.'),
        ('mp3/*.mp3', '.'),
        ('video/trolley.m4v', 'video'),
        ('video/easy.mp4', 'video'),
        ('video/start-stop.mp4', 'video'),
        ('video/full.mp4', 'video'),
        ('help.pdf', '.')
    ],
    hiddenimports=['mpv'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["windows-setup-hook.py"],
    excludes=[],
    noarchive=False,
    optimize=0,
)
splash = Splash('image/splash.png',
                binaries=a.binaries,
                datas=a.datas)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    [],
    exclude_binaries=True,
    name='trolley-windows',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    splash.binaries,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='trolley-windows',
)
