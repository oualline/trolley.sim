# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['brake_ui.py', 'controller.py', 'main.py', 'mode_window.py', 'sim_ui4.py', 'sound.py', 'state.py', 'video.py'],
    pathex=[],
    binaries=[
        ('image/*.png', 'image'),
        ('image/*.svg', 'image'),
        # libmpv is loaded at runtime via ctypes; bundle the system library so
        # the app runs on machines that don't have mpv installed.
        ('/usr/lib/x86_64-linux-gnu/libmpv.so.2', '.'),
    ],
    datas=[
	('image/splash.png', '.'),
        ('mp3/*.mp3', 'mp3'),        # sound.py looks in <app dir>/mp3
        ('video/trolley.m4v', 'video'),
        ('video/attract.mp4', 'video'),
        # Tutorial popups are loaded at run time with uic.loadUi(); they are
        # not compiled into Python, so they must ship as data files.
        ('*.ui', '.'),
        ('help.pdf', '.')
    ],
    hiddenimports=['mpv'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["linux-setup-hook.py"],
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
    a.binaries,
    a.datas,
    [],
    name='trolley-linux',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
