# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification for building VoiceClone Studio on macOS (.app bundle).
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
base_dir = Path.cwd()

datas = [
    (str(base_dir / "voiceclone" / "app" / "ui" / "styles"), "voiceclone/app/ui/styles"),
]

hidden_imports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "platformdirs",
    "soundfile",
    "sounddevice",
    "librosa",
    "pydub",
    "pyloudnorm",
    "noisereduce",
    "numpy",
    "sqlite3",
] + collect_submodules("voiceclone")

a = Analysis(
    [str(base_dir / "voiceclone" / "main.py")],
    pathex=[str(base_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
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
    name="VoiceCloneStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name="VoiceCloneStudio",
)

app = BUNDLE(
    coll,
    name="VoiceCloneStudio.app",
    icon=None,
    bundle_identifier="com.voiceclone.studio",
    info_plist={
        "NSMicrophoneUsageDescription": "VoiceClone Studio requires microphone access to record voice reference samples.",
        "NSHighResolutionCapable": "True",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "12.0",
    },
)

