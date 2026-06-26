# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['brake_ui.py', 'controller.py', 'main.py', 'mode_window.py', 'sim_ui4.py', 'sound.py', 'state.py', 'video.py', 'video_player.py'],
    pathex=[],
    binaries=[
        ('image/*.png', 'image'),
        ('image/*.svg', 'image'),
        # libmpv is loaded at runtime via ctypes; bundle the Homebrew library so
        # the app runs on machines without mpv installed.
        # Install mpv first: brew install mpv
        # Then adjust the path below if needed (arm64 uses /opt/homebrew, x86 uses /usr/local).
        ('/usr/local/Cellar/mpv/0.41.0_6/lib/libmpv.2.dylib', '.'),
    ],
    datas=[
        ('mp3/*.mp3', 'mp3'),
        ('video/trolley.m4v', 'video'),
        ('video/easy.mp4', 'video'),
        ('video/start-stop.mp4', 'video'),
        ('video/full.mp4', 'video'),
        ('help.pdf', '.')
    ],
    hiddenimports=['mpv'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
#splash = Splash('splash.png',
#                binaries=a.binaries,
#                datas=a.datas)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='trolley-macos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
