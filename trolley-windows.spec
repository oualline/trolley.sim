# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['brake_ui.py', 'controller.py', 'main.py', 'mode_window.py', 'sim_ui4.py', 'sound.py', 'state.py', 'video_player.py'],
    pathex=[],
    binaries=[
	('C:\\Program Files\\VideoLAN\\VLC\\', 'VLC'),
	('image/*.png', '.'),
	('image/*.svg', '.')
    ],
    datas=[
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
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='trolley-windows',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
