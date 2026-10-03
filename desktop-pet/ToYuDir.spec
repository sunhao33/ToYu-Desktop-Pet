# -*- mode: python ; coding: utf-8 -*-
# OneDir (folder) build: no runtime extraction, so AV temp-scanning cannot break startup.

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
    noarchive=True,  # 不打包 base_library.zip：火绒会把内嵌 zip 当威胁删除，
                     # 导致 "Failed to import encodings module" 无法启动
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ToYu',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources\\toyu_icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ToYu',
)
