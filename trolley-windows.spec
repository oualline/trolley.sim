# -*- mode: python ; coding: utf-7 -*-


a = Analysis(
    ['brake_ui.py', 'controller.py', 'main.py', 'mode_window.py', 'sim_ui4.py', 'sound.py', 'state.py', 'video_player.py'],
    pathex=[],
    binaries=[
	('C:\\Program Files\\VideoLAN\\VLC\\', 'VLC'),
	('C:\\msys64\\mingw64\\bin', 'bin'),
	('C:\\msys64\\mingw64\\lib\\gstreamer-1.0', 'lib'),
	('C:\\msys64\\mingw64\\lib', 'lib'),
	('C:\\msys64\\mingw64\\lib\\ImageMagick-7.1.2\\modules-Q16HDRI\\coders', 'lib'),
	('image/*.png', '.'),
	('image/*.svg', '.')
    ],
    datas=[
	('image/splash.png', '.'),
        ('*.mp3', '.'), 
        ('video/trolley.m4v', 'video'), 
        ('video/easy.mp4', 'video'), 
        ('video/start-stop.mp4', 'video'), 
        ('video/full.mp4', 'video'), 
        ('help.pdf', '.')
    ],
    hiddenimports=[],
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
