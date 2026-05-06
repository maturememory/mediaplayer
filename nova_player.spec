# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Nova Media Player.

Build with:
    pyinstaller nova_player.spec --noconfirm --clean
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hiddenimports = []
for package in (
    "PIL",
    "vlc",
    "whisper",
    "torch",
    "torchaudio",
    "tiktoken",
    "numpy",
):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

datas = []
for package in ("whisper", "tiktoken"):
    try:
        datas += collect_data_files(package)
    except Exception:
        pass


a = Analysis(
    ["nova_player.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NovaMediaPlayer",
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Nova Media Player",
)
