# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('resources/toyu_pet.png', 'resources'), ('resources/tv_pet.png', 'resources'), ('resources/toyu_icon.ico', 'resources'), ('resources/toyu_128.png', 'resources'), ('resources/house.png', 'resources'), ('resources/knock.wav', 'resources'), ('resources/acc_hat.png', 'resources'), ('resources/acc_umbrella.png', 'resources'), ('resources/acc_icecream.png', 'resources'), ('resources/acc_bow.png', 'resources'), ('resources/acc_crown.png', 'resources'), ('resources/acc_glasses.png', 'resources'), ('resources/acc_wand.png', 'resources')],
    hiddenimports=['psutil', 'win32gui', 'win32process'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    name='ToYu',
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
    icon=['resources\\toyu_icon.ico'],
)
